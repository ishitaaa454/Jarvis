"""Placeholder integration service for later phases.

Future responsibility:
- Calendar and unread email summaries
- News / current-affairs feeds
- Local AI (e.g. Ollama) for optional assistant reasoning
- Third-party connectors without embedding them in the core API layer

Phase 1 does not call Google, Microsoft, or local AI APIs.
"""

from __future__ import annotations


class IntegrationService:
    """Scaffold for calendar, email, news, and local AI integrations."""

    def fetch_calendar_summary(self) -> None:
        """Return today's calendar overview."""
        raise NotImplementedError("Calendar integration will be added in a later phase.")

    def fetch_unread_email_count(self) -> None:
        """Return unread email counts from configured accounts."""
        raise NotImplementedError("Email integration will be added in a later phase.")

    def fetch_news_headlines(self) -> None:
        """Return current-affairs headlines for the dashboard."""
        raise NotImplementedError("News integration will be added in a later phase.")

    def ask_local_ai(self, prompt: str) -> None:
        """Send a prompt to a local AI runtime."""
        raise NotImplementedError(
            f"Local AI is not available in Phase 1 (prompt={prompt!r})."
        )
