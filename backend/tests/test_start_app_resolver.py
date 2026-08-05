"""StartAppResolver tests — the PowerShell runner is always injected, never real."""

from __future__ import annotations

import subprocess

import pytest

from app.services.workspace.start_app_resolver import (
    POWERSHELL_START_APPS_ARGS,
    StartAppResolver,
)


def test_fixed_command_has_no_interpolation() -> None:
    """The argv is a hard-coded tuple; nothing here can be built from user input."""
    assert POWERSHELL_START_APPS_ARGS[0] == "powershell.exe"
    assert "-Command" in POWERSHELL_START_APPS_ARGS
    joined = " ".join(POWERSHELL_START_APPS_ARGS)
    assert "Get-StartApps" in joined
    assert "{" not in joined  # no format-string placeholders


def test_list_apps_parses_json_output() -> None:
    payload = (
        '[{"Name":"Visual Studio Code","AppID":"vscode_appid"},'
        '{"Name":"Microsoft Teams","AppID":"teams_appid"}]'
    )

    def fake_runner(args: list[str], timeout: float) -> str:
        assert args == list(POWERSHELL_START_APPS_ARGS)
        return payload

    resolver = StartAppResolver(runner=fake_runner)
    apps = resolver.list_apps()
    assert len(apps) == 2
    assert apps[0].name == "Visual Studio Code"
    assert apps[0].app_id == "vscode_appid"


def test_list_apps_handles_single_object_json() -> None:
    def fake_runner(args, timeout):
        return '{"Name":"Spotify","AppID":"spotify_appid"}'

    resolver = StartAppResolver(runner=fake_runner)
    apps = resolver.list_apps()
    assert len(apps) == 1
    assert apps[0].name == "Spotify"


def test_list_apps_handles_empty_output() -> None:
    resolver = StartAppResolver(runner=lambda args, timeout: "")
    assert resolver.list_apps() == []


def test_list_apps_handles_invalid_json() -> None:
    resolver = StartAppResolver(runner=lambda args, timeout: "not json at all")
    assert resolver.list_apps() == []


def test_list_apps_handles_timeout() -> None:
    def fake_runner(args, timeout):
        raise subprocess.TimeoutExpired(cmd="powershell", timeout=timeout)

    resolver = StartAppResolver(runner=fake_runner)
    assert resolver.list_apps() == []


def test_list_apps_handles_runner_exception() -> None:
    def fake_runner(args, timeout):
        raise RuntimeError("boom")

    resolver = StartAppResolver(runner=fake_runner)
    assert resolver.list_apps() == []


def test_resolve_exact_match() -> None:
    def fake_runner(args, timeout):
        return '[{"Name":"Microsoft Teams","AppID":"teams_appid"}]'

    resolver = StartAppResolver(runner=fake_runner)
    app = resolver.resolve("Microsoft Teams")
    assert app is not None
    assert app.app_id == "teams_appid"


def test_resolve_case_insensitive_and_partial_match() -> None:
    def fake_runner(args, timeout):
        return '[{"Name":"Microsoft Teams","AppID":"teams_appid"}]'

    resolver = StartAppResolver(runner=fake_runner)
    assert resolver.resolve("microsoft teams") is not None
    assert resolver.resolve("Teams") is not None


def test_resolve_not_found_returns_none() -> None:
    resolver = StartAppResolver(runner=lambda args, timeout: "[]")
    assert resolver.resolve("Nonexistent App") is None


def test_results_are_cached_until_ttl_expires() -> None:
    call_count = {"n": 0}

    def fake_runner(args, timeout):
        call_count["n"] += 1
        return '[{"Name":"Spotify","AppID":"spotify_appid"}]'

    resolver = StartAppResolver(runner=fake_runner, cache_ttl_seconds=60.0)
    resolver.list_apps()
    resolver.list_apps()
    assert call_count["n"] == 1


def test_force_refresh_bypasses_cache() -> None:
    call_count = {"n": 0}

    def fake_runner(args, timeout):
        call_count["n"] += 1
        return "[]"

    resolver = StartAppResolver(runner=fake_runner, cache_ttl_seconds=60.0)
    resolver.list_apps()
    resolver.list_apps(force_refresh=True)
    assert call_count["n"] == 2


def test_invalidate_cache_forces_rediscovery() -> None:
    call_count = {"n": 0}

    def fake_runner(args, timeout):
        call_count["n"] += 1
        return "[]"

    resolver = StartAppResolver(runner=fake_runner, cache_ttl_seconds=60.0)
    resolver.list_apps()
    resolver.invalidate_cache()
    resolver.list_apps()
    assert call_count["n"] == 2


def test_default_runner_never_uses_shell_true(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = {}

    def fake_run(args, **kwargs):
        captured.update(kwargs)
        captured["args"] = args

        class Result:
            stdout = "[]"

        return Result()

    monkeypatch.setattr(subprocess, "run", fake_run)
    resolver = StartAppResolver()
    resolver.list_apps()
    assert captured["shell"] is False
    assert captured["args"] == list(POWERSHELL_START_APPS_ARGS)
