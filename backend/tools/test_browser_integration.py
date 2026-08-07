#!/usr/bin/env python3
"""Manual browser integration checks (approved destinations only)."""

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
from app.services.browser import BrowserIntegrationService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Test Jarvis browser destinations.")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--destinations", action="store_true")
    parser.add_argument("--focus", default=None)
    parser.add_argument("--open", default=None, dest="open_id")
    return parser.parse_args()


async def run(args: argparse.Namespace) -> int:
    settings = get_settings()
    setup_logging(settings.log_level)
    service = BrowserIntegrationService(settings)
    await service.on_startup()
    try:
        if args.status or not any([args.destinations, args.focus, args.open_id]):
            status = service.get_status()
            print(f"status={status.status.value} mode={status.mode.value}")
            print(f"exact_tab_focus={status.exact_tab_focus_available}")
            if status.reason:
                print(f"reason={status.reason}")
        if args.destinations or args.status:
            for dest in service.list_destinations():
                print(
                    f"{dest.id:12s}  known_open={dest.known_open}  "
                    f"exact={dest.exact_focus_available}"
                )
        if args.open_id:
            result = await service.open_destination(args.open_id)
            print(result.model_dump())
        if args.focus:
            result = await service.focus_destination(args.focus)
            print(result.model_dump())
        return 0
    finally:
        await service.shutdown()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run(parse_args())))
