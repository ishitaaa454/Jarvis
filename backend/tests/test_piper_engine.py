"""PiperEngine unit tests — no real Piper executable required."""

from __future__ import annotations

import subprocess
import wave
from pathlib import Path

import pytest

from app.services.tts.piper_engine import (
    PiperEngine,
    PiperEngineError,
    validate_piper_executable,
    validate_voice_model,
)

WELCOME_1 = "Welcome back, Ishita. Initializing your workspace."


def _write_silent_wav(path: Path, *, duration: float = 0.05, rate: int = 22050) -> None:
    frames = int(rate * duration)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(b"\x00\x00" * frames)


def _voice_pair(tmp_path: Path) -> tuple[Path, Path]:
    model = tmp_path / "en_GB-alan-medium.onnx"
    config = tmp_path / "en_GB-alan-medium.onnx.json"
    model.write_bytes(b"fake-onnx")
    config.write_text("{}", encoding="utf-8")
    return model, config


class FakeRunner:
    """CompletedProcess-like Piper subprocess stand-in."""

    def __init__(self, mode: str = "success") -> None:
        self.mode = mode
        self.calls: list[tuple[list[str], str, float]] = []

    def run(
        self,
        args: list[str],
        *,
        input_text: str,
        timeout: float,
    ) -> subprocess.CompletedProcess[bytes]:
        self.calls.append((list(args), input_text, timeout))
        if self.mode == "timeout":
            raise subprocess.TimeoutExpired(cmd=args, timeout=timeout)
        if self.mode == "missing_exe":
            raise FileNotFoundError("piper")

        out_path = Path(args[args.index("--output_file") + 1])
        if self.mode == "empty":
            out_path.write_bytes(b"")
            return subprocess.CompletedProcess(args, 0, b"", b"")
        if self.mode == "corrupt":
            out_path.write_bytes(b"not-a-wav-file")
            return subprocess.CompletedProcess(args, 0, b"", b"")
        if self.mode == "fail":
            return subprocess.CompletedProcess(args, 1, b"", b"synthesis boom")

        _write_silent_wav(out_path)
        return subprocess.CompletedProcess(args, 0, b"", b"")


def test_validate_piper_executable_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.tts.piper_engine.shutil.which", lambda _name: None)
    missing = tmp_path / "no-such-piper.exe"
    with pytest.raises(PiperEngineError) as exc:
        validate_piper_executable(missing)
    assert exc.value.code == "ENGINE_MISSING"


def test_validate_piper_executable_found(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.tts.piper_engine.shutil.which", lambda _name: None)
    exe = tmp_path / "piper.exe"
    exe.write_bytes(b"MZ")
    resolved = validate_piper_executable(exe)
    assert resolved == exe.resolve()


def test_validate_voice_model_missing_files(tmp_path: Path) -> None:
    model = tmp_path / "voice.onnx"
    config = tmp_path / "voice.onnx.json"
    with pytest.raises(PiperEngineError) as exc:
        validate_voice_model(model, config)
    assert exc.value.code == "MODEL_MISSING"


def test_validate_voice_model_invalid_suffix(tmp_path: Path) -> None:
    model = tmp_path / "voice.bin"
    config = tmp_path / "voice.json"
    model.write_bytes(b"x")
    config.write_text("{}", encoding="utf-8")
    with pytest.raises(PiperEngineError) as exc:
        validate_voice_model(model, config)
    assert exc.value.code == "MODEL_INVALID"


def test_validate_voice_model_ok(tmp_path: Path) -> None:
    model, config = _voice_pair(tmp_path)
    validate_voice_model(model, config)


def test_synthesize_success_with_fake_runner(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.tts.piper_engine.shutil.which", lambda _name: None)
    exe = tmp_path / "piper.exe"
    exe.write_bytes(b"MZ")
    model, config = _voice_pair(tmp_path)
    runner = FakeRunner("success")
    engine = PiperEngine(
        executable=exe,
        model_path=model,
        config_path=config,
        temp_dir=tmp_path / "tts-tmp",
        delete_temp=True,
        runner=runner,
    )
    engine.validate()
    assert engine.is_ready is True

    audio = engine.synthesize(WELCOME_1)
    assert audio.text == WELCOME_1
    assert audio.sample_rate == 22050
    assert audio.duration_seconds > 0
    assert Path(audio.path).exists()
    assert len(runner.calls) == 1
    assert runner.calls[0][1] == WELCOME_1


def test_synthesize_timeout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.tts.piper_engine.shutil.which", lambda _name: None)
    exe = tmp_path / "piper.exe"
    exe.write_bytes(b"MZ")
    model, config = _voice_pair(tmp_path)
    engine = PiperEngine(
        executable=exe,
        model_path=model,
        config_path=config,
        temp_dir=tmp_path / "tts-tmp",
        runner=FakeRunner("timeout"),
        timeout_seconds=1.0,
    )
    with pytest.raises(PiperEngineError) as exc:
        engine.synthesize("hello")
    assert exc.value.code == "SYNTHESIS_TIMEOUT"


def test_synthesize_rejects_empty_wav(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.tts.piper_engine.shutil.which", lambda _name: None)
    exe = tmp_path / "piper.exe"
    exe.write_bytes(b"MZ")
    model, config = _voice_pair(tmp_path)
    engine = PiperEngine(
        executable=exe,
        model_path=model,
        config_path=config,
        temp_dir=tmp_path / "tts-tmp",
        runner=FakeRunner("empty"),
    )
    with pytest.raises(PiperEngineError) as exc:
        engine.synthesize("hello")
    assert exc.value.code == "INVALID_WAV"


def test_synthesize_rejects_corrupt_wav(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.tts.piper_engine.shutil.which", lambda _name: None)
    exe = tmp_path / "piper.exe"
    exe.write_bytes(b"MZ")
    model, config = _voice_pair(tmp_path)
    engine = PiperEngine(
        executable=exe,
        model_path=model,
        config_path=config,
        temp_dir=tmp_path / "tts-tmp",
        runner=FakeRunner("corrupt"),
    )
    with pytest.raises(PiperEngineError) as exc:
        engine.synthesize("hello")
    assert exc.value.code == "INVALID_WAV"


def test_synthesize_empty_text_rejected(tmp_path: Path) -> None:
    model, config = _voice_pair(tmp_path)
    engine = PiperEngine(
        executable=tmp_path / "piper.exe",
        model_path=model,
        config_path=config,
        validated=True,
        runner=FakeRunner(),
    )
    engine._executable = tmp_path / "piper.exe"
    with pytest.raises(PiperEngineError) as exc:
        engine.synthesize("   ")
    assert exc.value.code == "EMPTY_TEXT"
