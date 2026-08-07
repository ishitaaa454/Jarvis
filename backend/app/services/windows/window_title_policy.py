"""Window title privacy policy for Phase 7."""

from __future__ import annotations

import re

from app.models.window import WindowTitleMode

# Apps whose raw titles must never leak private content in SAFE mode.
PROTECTED_APP_TITLES: dict[str, str] = {
    "gmail": "Gmail",
    "teams": "Microsoft Teams",
    "whatsapp": "WhatsApp",
    "spotify": "Spotify",
    "news": "News",
}


def sanitize_window_title(
    *,
    application_id: str,
    raw_title: str,
    display_name: str,
    mode: WindowTitleMode,
    allow_full: bool = False,
) -> str:
    """Return a privacy-safe display title.

    FULL mode is development-only (`allow_full`).
    """
    if mode == WindowTitleMode.HIDDEN:
        return display_name or application_id

    if mode == WindowTitleMode.FULL and allow_full:
        return raw_title.strip() or display_name

    # SAFE (default) — never expose private messaging/email/media titles.
    if application_id in PROTECTED_APP_TITLES:
        return PROTECTED_APP_TITLES[application_id]

    title = (raw_title or "").strip()
    if not title:
        return display_name

    if application_id == "vscode":
        # "file — project - Visual Studio Code" / "project - Visual Studio Code"
        cleaned = re.sub(r"\s*[-—]\s*Visual Studio Code\s*$", "", title, flags=re.IGNORECASE)
        cleaned = cleaned.strip(" -—")
        return cleaned or "Visual Studio Code"

    if application_id == "chrome":
        lower = title.lower()
        if "gmail" in lower or "mail.google" in lower:
            return "Gmail"
        if "news.google" in lower or "google news" in lower:
            return "News"
        if "localhost:5173" in lower or "127.0.0.1:5173" in lower:
            return "Jarvis Dashboard"
        return "Chrome window"

    # Generic: strip trailing " - AppName"
    pattern = re.escape(display_name)
    cleaned = re.sub(rf"\s*[-—]\s*{pattern}\s*$", "", title, flags=re.IGNORECASE)
    cleaned = cleaned.strip(" -—")
    return cleaned or display_name
