#!/usr/bin/env python3
"""Manual Phase 7 window inventory tool."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import get_settings
from app.core.logging_config import setup_logging
from app.services.windows import WindowInventoryService
from app.services.workspace import WorkspaceService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect Jarvis window inventory.")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--recent", action="store_true")
    parser.add_argument("--app", default=None)
    parser.add_argument("--include-safe-titles", action="store_true")
    return parser.parse_args()


async def run(args: argparse.Namespace) -> int:
    settings = get_settings()
    setup_logging(settings.log_level)
    workspace = WorkspaceService(settings=settings)
    service = WindowInventoryService(
        settings,
        app_resolver=workspace.list_application_definitions,
    )
    await service.start()
    try:
        snap = await service.refresh_now()
        if args.recent:
            for item in service.get_recent():
                print(f"{item.application_id:12s}  {item.display_title}")
            return 0
        for app in snap.applications:
            if args.app and app.application_id != args.app:
                continue
            print(
                f"{app.application_id:12s}  running={app.running}  "
                f"windows={app.window_count}  favourite={app.favourite}"
            )
            if args.include_safe_titles or args.app:
                for win in app.windows:
                    state = (
                        "FOREGROUND"
                        if win.foreground
                        else "MINIMIZED"
                        if win.minimized
                        else "BACKGROUND"
                    )
                    print(f"  {win.window_id}  {state:10s}  {win.display_title}")
        return 0
    finally:
        await service.shutdown()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run(parse_args())))
