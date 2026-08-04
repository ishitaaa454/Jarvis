"""Validate Piper installation and synthesize speech via subprocess.

Integration approach (Windows):
    Prefer a local ``piper.exe`` from the official Piper Windows release.
    Invoke it with ``subprocess.run(..., shell=False)`` and text on stdin.
    Voice files are ``.onnx`` + ``.onnx.json`` (never auto-downloaded at startup).
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
import time
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol

from app.models.tts import SynthesizedAudio

logger = logging.getLogger(__name__)


class PiperEngineError(Exception):
    def __init__(self, message: str, *, code: str = "PIPER_ERROR") -> None:
        super().__init__(message)
        self.code = code
        self.user_message = message


class PiperProcessRunner(Protocol):
    def run(
        self,
        args: list[str],
        *,
        input_text: str,
        timeout: float,
    ) -> subprocess.CompletedProcess[bytes]: ...


@dataclass
class DefaultPiperRunner:
    def run(
        self,
        args: list[str],
        *,
        input_text: str,
        timeout: float,
    ) -> subprocess.CompletedProcess[bytes]:
        return subprocess.run(
            args,
            input=input_text.encode("utf-8"),
            capture_output=True,
            timeout=timeout,
            shell=False,
            check=False,
        )


def validate_piper_executable(path: Path | None) -> Path:
    """Return a usable Piper executable path or raise PiperEngineError."""
    candidates: list[Path] = []
    if path is not None:
        candidates.append(path)
    which = shutil.which("piper") or shutil.which("piper.exe")
    if which:
        candidates.append(Path(which))

    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()

    raise PiperEngineError(
        "Piper executable was not found. Install Piper for Windows and set "
        "PIPER_EXECUTABLE_PATH, or add piper.exe to PATH.",
        code="ENGINE_MISSING",
    )


def validate_voice_model(model_path: Path, config_path: Path) -> None:
    if not model_path.exists() or not model_path.is_file():
        raise PiperEngineError(
            f"Piper voice model not found: {model_path.name}",
            code="MODEL_MISSING",
        )
    if not config_path.exists() or not config_path.is_file():
        raise PiperEngineError(
            f"Piper voice config not found: {config_path.name}",
            code="MODEL_MISSING",
        )
    if model_path.suffix.lower() != ".onnx":
        raise PiperEngineError(
            "Piper voice model must be an .onnx file.",
            code="MODEL_INVALID",
        )
    if not config_path.name.endswith(".onnx.json"):
        raise PiperEngineError(
            "Piper voice config must be an .onnx.json file.",
            code="MODEL_INVALID",
        )
    try:
        model_path.open("rb").close()
        config_path.open("rb").close()
    except OSError as exc:
        raise PiperEngineError(
            f"Unable to read Piper voice files: {exc}",
            code="MODEL_UNREADABLE",
        ) from exc


class PiperEngine:
    """Isolated Piper synthesis adapter."""

    def __init__(
        self,
        *,
        executable: Path | None,
        model_path: Path,
        config_path: Path,
        length_scale: float = 1.08,
        noise_scale: float = 0.667,
        noise_width: float = 0.80,
        timeout_seconds: float = 30.0,
        temp_dir: Path | None = None,
        delete_temp: bool = True,
        runner: PiperProcessRunner | None = None,
        validated: bool = False,
    ) -> None:
        self._configured_executable = executable
        self._executable: Path | None = None
        self.model_path = model_path
        self.config_path = config_path
        self.length_scale = length_scale
        self.noise_scale = noise_scale
        self.noise_width = noise_width
        self.timeout_seconds = timeout_seconds
        self.temp_dir = temp_dir
        self.delete_temp = delete_temp
        self._runner = runner or DefaultPiperRunner()
        self._validated = validated
        self._last_error: str | None = None
        self._active_process: subprocess.Popen[bytes] | None = None
        self._cache: dict[str, Path] = {}

    @property
    def last_error(self) -> str | None:
        return self._last_error

    @property
    def is_ready(self) -> bool:
        return self._validated and self._executable is not None

    def validate(self) -> None:
        try:
            self._executable = validate_piper_executable(self._configured_executable)
            validate_voice_model(self.model_path, self.config_path)
            if self.temp_dir is not None:
                self.temp_dir.mkdir(parents=True, exist_ok=True)
            self._validated = True
            self._last_error = None
            logger.info(
                "Piper engine validated executable=%s model=%s",
                self._executable,
                self.model_path.name,
            )
        except PiperEngineError as exc:
            self._validated = False
            self._executable = None
            self._last_error = exc.user_message
            raise

    def synthesize(self, text: str) -> SynthesizedAudio:
        if not text.strip():
            raise PiperEngineError("Cannot synthesize empty text.", code="EMPTY_TEXT")
        if not self._validated or self._executable is None:
            self.validate()
        assert self._executable is not None

        cached = self._cache.get(text)
        if cached is not None and cached.exists():
            return self._inspect_wav(cached, text=text)

        temp_dir = self.temp_dir or Path(tempfile.gettempdir()) / "jarvis-tts"
        temp_dir.mkdir(parents=True, exist_ok=True)
        out_path = Path(
            tempfile.mkstemp(prefix="jarvis-tts-", suffix=".wav", dir=str(temp_dir))[1]
        )

        args = [
            str(self._executable),
            "--model",
            str(self.model_path),
            "--output_file",
            str(out_path),
            "--length_scale",
            str(self.length_scale),
            "--noise_scale",
            str(self.noise_scale),
            "--noise_w",
            str(self.noise_width),
        ]

        started = time.perf_counter()
        try:
            result = self._runner.run(
                args,
                input_text=text,
                timeout=self.timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            self._last_error = "Piper synthesis timed out."
            self._cleanup_file(out_path)
            raise PiperEngineError(self._last_error, code="SYNTHESIS_TIMEOUT") from exc
        except FileNotFoundError as exc:
            self._validated = False
            self._last_error = "Piper executable disappeared."
            raise PiperEngineError(self._last_error, code="ENGINE_MISSING") from exc

        duration = time.perf_counter() - started
        if result.returncode != 0:
            stderr = (result.stderr or b"").decode("utf-8", errors="replace")[:500]
            self._last_error = f"Piper synthesis failed: {stderr or 'unknown error'}"
            self._cleanup_file(out_path)
            raise PiperEngineError(self._last_error, code="SYNTHESIS_FAILED")

        audio = self._inspect_wav(out_path, text=text)
        logger.info(
            "Piper synthesized text_len=%d duration=%.2fs wav=%.2fs",
            len(text),
            duration,
            audio.duration_seconds,
        )
        self._cache[text] = out_path
        return audio

    def stop(self) -> None:
        proc = self._active_process
        self._active_process = None
        if proc is not None and proc.poll() is None:
            try:
                proc.terminate()
                proc.wait(timeout=2)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    logger.exception("Failed to kill Piper process")

    def cleanup_cache(self) -> None:
        if not self.delete_temp:
            return
        for path in list(self._cache.values()):
            self._cleanup_file(path)
        self._cache.clear()

    def _inspect_wav(self, path: Path, *, text: str) -> SynthesizedAudio:
        if not path.exists() or path.stat().st_size == 0:
            self._cleanup_file(path)
            raise PiperEngineError(
                "Piper produced an empty audio file.",
                code="INVALID_WAV",
            )
        try:
            with wave.open(str(path), "rb") as wav:
                channels = wav.getnchannels()
                sample_width = wav.getsampwidth()
                sample_rate = wav.getframerate()
                frames = wav.getnframes()
                if channels < 1 or sample_width < 1 or sample_rate < 1 or frames < 1:
                    raise PiperEngineError(
                        "Generated WAV has invalid format.",
                        code="INVALID_WAV",
                    )
                duration = frames / float(sample_rate)
        except wave.Error as exc:
            self._cleanup_file(path)
            raise PiperEngineError(
                "Generated WAV is corrupted or unreadable.",
                code="INVALID_WAV",
            ) from exc

        return SynthesizedAudio(
            path=str(path),
            sample_rate=sample_rate,
            channels=channels,
            sample_width=sample_width,
            duration_seconds=duration,
            text=text,
        )

    @staticmethod
    def _cleanup_file(path: Path) -> None:
        try:
            if path.exists():
                path.unlink()
        except OSError:
            logger.warning("Failed to delete temporary TTS file %s", path)
