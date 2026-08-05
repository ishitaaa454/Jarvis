"""AppRegistry loading, validation, override, and ordering tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.core.config import Settings
from app.services.workspace.app_registry import AppRegistry, AppRegistryError

SAMPLE_CONFIG = {
    "profile": "default",
    "applications": [
        {
            "id": "vscode",
            "display_name": "Visual Studio Code",
            "enabled": True,
            "launch_type": "executable",
            "executable_candidates": ["code.cmd"],
            "configured_path": "",
            "process_names": ["Code.exe"],
            "window_title_patterns": ["Visual Studio Code"],
            "start_app_name": "Visual Studio Code",
            "order": 10,
        },
        {
            "id": "gmail",
            "display_name": "Gmail",
            "enabled": True,
            "launch_type": "browser_url",
            "process_names": ["chrome.exe"],
            "url": "https://mail.google.com/",
            "order": 30,
        },
        {
            "id": "disabled_app",
            "display_name": "Disabled App",
            "enabled": False,
            "launch_type": "executable",
            "executable_candidates": ["disabled.exe"],
            "order": 5,
        },
        {
            "id": "chrome",
            "display_name": "Google Chrome",
            "enabled": True,
            "launch_type": "executable",
            "executable_candidates": ["chrome.exe"],
            "process_names": ["chrome.exe"],
            "order": 20,
        },
    ],
}


def write_config(tmp_path: Path, data: dict) -> Path:
    path = tmp_path / "applications.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


@pytest.fixture
def settings() -> Settings:
    return Settings(environment="development")


def test_loads_and_orders_applications(tmp_path: Path, settings: Settings) -> None:
    config_path = write_config(tmp_path, SAMPLE_CONFIG)
    registry = AppRegistry(settings=settings, config_path=config_path)

    assert registry.profile == "default"
    all_apps = registry.all_applications()
    assert len(all_apps) == 4

    enabled = registry.enabled_in_order()
    assert [a.id for a in enabled] == ["vscode", "chrome", "gmail"]


def test_disabled_app_excluded_from_enabled_order(tmp_path: Path, settings: Settings) -> None:
    config_path = write_config(tmp_path, SAMPLE_CONFIG)
    registry = AppRegistry(settings=settings, config_path=config_path)
    ids = [a.id for a in registry.enabled_in_order()]
    assert "disabled_app" not in ids


def test_get_returns_application_by_id(tmp_path: Path, settings: Settings) -> None:
    config_path = write_config(tmp_path, SAMPLE_CONFIG)
    registry = AppRegistry(settings=settings, config_path=config_path)
    app = registry.get("gmail")
    assert app is not None
    assert app.display_name == "Gmail"
    assert registry.get("does_not_exist") is None


def test_missing_config_raises_registry_error(tmp_path: Path, settings: Settings) -> None:
    missing = tmp_path / "does_not_exist.json"
    with pytest.raises(AppRegistryError):
        AppRegistry(settings=settings, config_path=missing)


def test_invalid_json_raises_registry_error(tmp_path: Path, settings: Settings) -> None:
    path = tmp_path / "bad.json"
    path.write_text("{not valid json", encoding="utf-8")
    with pytest.raises(AppRegistryError):
        AppRegistry(settings=settings, config_path=path)


def test_duplicate_ids_raise_registry_error(tmp_path: Path, settings: Settings) -> None:
    data = json.loads(json.dumps(SAMPLE_CONFIG))
    data["applications"].append(dict(data["applications"][0]))
    path = write_config(tmp_path, data)
    with pytest.raises(AppRegistryError):
        AppRegistry(settings=settings, config_path=path)


def test_gmail_url_override_from_settings(tmp_path: Path) -> None:
    settings = Settings(environment="development", gmail_url="https://mail.google.com/custom")
    config_path = write_config(tmp_path, SAMPLE_CONFIG)
    registry = AppRegistry(settings=settings, config_path=config_path)
    app = registry.get("gmail")
    assert app is not None
    assert app.url == "https://mail.google.com/custom"


def test_chrome_path_override_from_settings(tmp_path: Path) -> None:
    settings = Settings(environment="development", chrome_executable_path="C:/Custom/chrome.exe")
    config_path = write_config(tmp_path, SAMPLE_CONFIG)
    registry = AppRegistry(settings=settings, config_path=config_path)
    app = registry.get("chrome")
    assert app is not None
    assert app.configured_path == "C:/Custom/chrome.exe"


def test_no_override_leaves_config_untouched(tmp_path: Path, settings: Settings) -> None:
    config_path = write_config(tmp_path, SAMPLE_CONFIG)
    registry = AppRegistry(settings=settings, config_path=config_path)
    app = registry.get("chrome")
    assert app is not None
    assert app.configured_path == ""


def test_reload_picks_up_file_changes(tmp_path: Path, settings: Settings) -> None:
    config_path = write_config(tmp_path, SAMPLE_CONFIG)
    registry = AppRegistry(settings=settings, config_path=config_path)
    assert len(registry.all_applications()) == 4

    smaller = json.loads(json.dumps(SAMPLE_CONFIG))
    smaller["applications"] = smaller["applications"][:1]
    config_path.write_text(json.dumps(smaller), encoding="utf-8")

    registry.reload()
    assert len(registry.all_applications()) == 1


def test_real_default_applications_config_loads(settings: Settings) -> None:
    """The shipped config/applications.json must always be valid."""
    registry = AppRegistry(settings=settings)
    apps = registry.enabled_in_order()
    assert len(apps) > 0
