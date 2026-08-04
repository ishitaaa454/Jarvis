"""UTC timestamp helpers."""

from datetime import datetime, timezone


def utc_now() -> datetime:
    """Return the current UTC time as a timezone-aware datetime."""
    return datetime.now(timezone.utc)


def utc_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return utc_now().isoformat()
