"""Chrome/browser control: ensure Chrome is available, open validated HTTPS URLs.

URLs are validated before ever being passed to a subprocess. javascript:/data:/file:
schemes are always rejected; only https is allowed by default, with http allowed
for localhost/127.0.0.1 in development. Each workspace run dedupes URLs so the
same destination is not reopened twice.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable, Protocol

from app.core.config import validate_https_url
from app.services.workspace.process_manager import ProcessManager

logger = logging.getLogger(__name__)

CHROME_PROCESS_NAMES = ["chrome.exe"]

ChromeResolver = Callable[[], "Path | None"]


class UrlLauncher(Protocol):
    def launch_executable(self, path: Path, args: list[str]) -> int: ...


def is_url_allowed(url: str, *, allow_localhost_http: bool = False) -> bool:
    return validate_https_url(url, allow_localhost_http=allow_localhost_http)


class BrowserController:
    def __init__(
        self,
        *,
        resolve_chrome: ChromeResolver,
        process_manager: ProcessManager,
        launcher: UrlLauncher,
        allow_localhost_http: bool = False,
    ) -> None:
        self._resolve_chrome = resolve_chrome
        self._process_manager = process_manager
        self._launcher = launcher
        self._allow_localhost_http = allow_localhost_http
        self._opened_urls: set[str] = set()

    def reset_session(self) -> None:
        """Clear per-run URL dedupe state. Call at the start of each workspace run."""
        self._opened_urls.clear()

    def is_chrome_running(self) -> bool:
        return self._process_manager.is_running(CHROME_PROCESS_NAMES)

    def already_opened(self, url: str) -> bool:
        return url in self._opened_urls

    def open_url(self, url: str) -> tuple[bool, str | None]:
        """Validate, dedupe, and launch Chrome with the given URL.

        Returns (success, error_message). Never raises.
        """
        if not is_url_allowed(url, allow_localhost_http=self._allow_localhost_http):
            logger.warning("Rejected unsafe or disallowed workspace URL")
            return False, "URL rejected by security policy"

        if url in self._opened_urls:
            return True, None

        chrome = self._resolve_chrome()
        if chrome is None:
            return False, "Chrome executable could not be resolved"

        try:
            self._launcher.launch_executable(chrome, [url])
        except Exception:
            logger.exception("Failed to launch browser for workspace URL")
            return False, "Failed to launch browser"

        self._opened_urls.add(url)
        return True, None
