"""Placeholder workspace service for later phases.

Future responsibility:
- Launch and focus Windows applications (VS Code, Chrome, Teams, etc.)
- Open web destinations (Gmail, news dashboard)
- Coordinate the "initialize workspace" sequence after wake

Phase 1 does not automate or launch any applications.
"""

from __future__ import annotations


class WorkspaceService:
    """Scaffold for Windows application / workspace control."""

    def initialize_workspace(self) -> None:
        """Run the full workspace initialization sequence."""
        raise NotImplementedError(
            "Workspace initialization will be implemented in a later phase."
        )

    def open_application(self, app_name: str) -> None:
        """Open or focus a configured application by name."""
        raise NotImplementedError(
            f"Application control is not available in Phase 1 (app={app_name!r})."
        )
