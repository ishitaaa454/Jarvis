"""Load, validate, and override the workspace application registry.

Reads config/applications.json (validated by ApplicationDefinition /
ApplicationsConfigFile) and applies environment-driven overrides for
well-known application ids (gmail/news URLs, chrome/vscode/teams/whatsapp/
spotify executable paths) so operators can customize without editing JSON.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from app.core.config import Settings, get_settings
from app.models.application import ApplicationDefinition, ApplicationsConfigFile

logger = logging.getLogger(__name__)

_URL_OVERRIDE_SETTINGS = {
    "gmail": "gmail_url",
    "news": "news_url",
}

_PATH_OVERRIDE_SETTINGS = {
    "chrome": "chrome_executable_path",
    "vscode": "vscode_executable_path",
    "teams": "teams_executable_path",
    "whatsapp": "whatsapp_executable_path",
    "spotify": "spotify_executable_path",
}


class AppRegistryError(Exception):
    """Raised when the workspace application registry cannot be loaded."""


class AppRegistry:
    def __init__(
        self,
        *,
        settings: Settings | None = None,
        config_path: Path | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._config_path = config_path or self._settings.resolved_workspace_config_path()
        self._config: ApplicationsConfigFile = self._load(self._config_path)

    @property
    def profile(self) -> str:
        return self._config.profile

    @property
    def config_path(self) -> Path:
        return self._config_path

    def reload(self) -> None:
        self._config = self._load(self._config_path)

    def _load(self, path: Path) -> ApplicationsConfigFile:
        try:
            raw_text = path.read_text(encoding="utf-8")
        except FileNotFoundError as exc:
            raise AppRegistryError(f"Workspace config not found: {path}") from exc
        except OSError as exc:
            raise AppRegistryError(f"Workspace config could not be read: {path}") from exc

        try:
            raw = json.loads(raw_text)
        except ValueError as exc:
            raise AppRegistryError(f"Workspace config is not valid JSON: {path}") from exc

        try:
            config = ApplicationsConfigFile.model_validate(raw)
        except Exception as exc:
            raise AppRegistryError(f"Workspace config failed validation: {exc}") from exc

        config.applications = [self._apply_overrides(app) for app in config.applications]
        return config

    def _apply_overrides(self, app: ApplicationDefinition) -> ApplicationDefinition:
        overrides: dict[str, object] = {}

        url_field = _URL_OVERRIDE_SETTINGS.get(app.id)
        if url_field:
            override_value = getattr(self._settings, url_field, "")
            if override_value:
                overrides["url"] = override_value

        path_field = _PATH_OVERRIDE_SETTINGS.get(app.id)
        if path_field:
            override_value = getattr(self._settings, path_field, "")
            if override_value:
                overrides["configured_path"] = override_value

        if not overrides:
            return app
        return app.model_copy(update=overrides)

    def all_applications(self) -> list[ApplicationDefinition]:
        return list(self._config.applications)

    def enabled_in_order(self) -> list[ApplicationDefinition]:
        apps = [app for app in self.all_applications() if app.enabled]
        return sorted(apps, key=lambda app: (app.order, app.id))

    def get(self, app_id: str) -> ApplicationDefinition | None:
        for app in self.all_applications():
            if app.id == app_id:
                return app
        return None
