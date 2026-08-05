"""ExecutableResolver resolution-order tests with fully injected dependencies."""

from __future__ import annotations

from pathlib import Path

from app.services.workspace.executable_resolver import ExecutableResolver


def test_configured_path_wins_when_it_exists(tmp_path: Path) -> None:
    exe = tmp_path / "app.exe"
    exe.write_text("binary")
    resolver = ExecutableResolver(env={}, search_roots=[], which=lambda name: None)
    result = resolver.resolve(configured_path=str(exe), candidates=["other.exe"])
    assert result == exe


def test_configured_path_missing_falls_back_to_candidates(tmp_path: Path) -> None:
    absolute_candidate = tmp_path / "candidate.exe"
    absolute_candidate.write_text("binary")
    resolver = ExecutableResolver(env={}, search_roots=[], which=lambda name: None)
    result = resolver.resolve(
        configured_path=str(tmp_path / "missing.exe"),
        candidates=[str(absolute_candidate)],
    )
    assert result == absolute_candidate


def test_absolute_candidate_used_when_present(tmp_path: Path) -> None:
    absolute_candidate = tmp_path / "candidate.exe"
    absolute_candidate.write_text("binary")
    resolver = ExecutableResolver(env={}, search_roots=[], which=lambda name: None)
    result = resolver.resolve(candidates=[str(absolute_candidate)])
    assert result == absolute_candidate


def test_which_used_for_relative_candidates() -> None:
    calls: list[str] = []

    def fake_which(name: str) -> str | None:
        calls.append(name)
        return r"C:\PATH\code.cmd" if name == "code.cmd" else None

    resolver = ExecutableResolver(env={}, search_roots=[], which=fake_which)
    result = resolver.resolve(candidates=["code.cmd", "code.exe"])
    assert result == Path(r"C:\PATH\code.cmd")
    assert calls[0] == "code.cmd"


def test_search_roots_used_as_last_resort(tmp_path: Path) -> None:
    root = tmp_path / "LocalAppData"
    target_dir = root / "Programs"
    target_dir.mkdir(parents=True)
    target = target_dir / "chrome.exe"
    target.write_text("binary")

    resolver = ExecutableResolver(env={}, search_roots=[root], which=lambda name: None)
    result = resolver.resolve(candidates=["chrome.exe"])
    assert result == target


def test_returns_none_when_nothing_resolves() -> None:
    resolver = ExecutableResolver(env={}, search_roots=[], which=lambda name: None)
    result = resolver.resolve(candidates=["nonexistent.exe"])
    assert result is None


def test_default_roots_built_from_env() -> None:
    env = {"LOCALAPPDATA": r"C:\Users\test\AppData\Local"}
    resolver = ExecutableResolver(env=env, which=lambda name: None)
    roots = resolver._search_roots  # noqa: SLF001 — testing internal wiring
    assert Path(r"C:\Users\test\AppData\Local") in roots


def test_empty_candidates_returns_none() -> None:
    resolver = ExecutableResolver(env={}, search_roots=[], which=lambda name: None)
    assert resolver.resolve(candidates=[]) is None
    assert resolver.resolve() is None
