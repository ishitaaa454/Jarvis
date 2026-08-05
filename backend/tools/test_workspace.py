#!/usr/bin/env python3
"""Test workspace launching using production WorkspaceService classes."""

from __future__ import annotations

import argparse
import asyncio
import signal
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import Settings, get_settings
from app.core.events import EventBus
from app.core.logging_config import setup_logging
from app.services.workspace import WorkspaceService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Test Jarvis workspace launching.")
    parser.add_argument("--list", action="store_true", help="List configured applications")
    parser.add_argument("--status", action="store_true", help="Show status without launching")
    parser.add_argument("--app", default=None, help="Open/focus one application id")
    parser.add_argument("--start", action="store_true", help="Run full default workspace")
    parser.add_argument("--no-focus", action="store_true", help="Disable focus_existing for this run")
    parser.add_argument("--focus-only", action="store_true", help="Focus app instead of open")
    return parser.parse_args()


async def run(args: argparse.Namespace) -> int:
    settings = get_settings()
    if args.no_focus:
        settings = Settings(**{**settings.model_dump(), "workspace_focus_existing": False})

    setup_logging(settings.log_level)
    bus = EventBus()
    service = WorkspaceService(settings=settings, event_bus=bus)
    await service.on_startup()

    stop = asyncio.Event()

    def _sig(*_a: object) -> None:
        stop.set()

    try:
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                asyncio.get_running_loop().add_signal_handler(sig, _sig)
            except NotImplementedError:
                signal.signal(sig, lambda *_: stop.set())
    except Exception:
        pass

    try:
        if args.list:
            apps = service.list_applications()
            for app in apps:
                print(
                    f"{app.order:3d}  {app.id:12s}  enabled={app.enabled}  "
                    f"type={app.launch_type.value}  resolved={app.resolved}  "
                    f"running={app.running}"
                )
            return 0

        if args.status:
            status = service.get_status()
            print(f"status={status.status.value} enabled={status.enabled}")
            print(f"configured={status.total_configured} enabled_count={status.total_enabled}")
            if status.last_error:
                print(f"last_error={status.last_error}")
            for app in service.list_applications():
                print(
                    f"  {app.id}: running={app.running} window={app.window_found} "
                    f"status={app.status.value}"
                )
            return 0

        if args.app:
            app_id = args.app.strip().lower()
            if args.focus_only:
                print(f"Focusing {app_id}...")
                result = await service.focus_application(app_id)
            else:
                print(f"Opening {app_id}...")
                result = await service.open_application(app_id)
            print(
                f"result={result.result} running={result.running} "
                f"window_found={result.window_found} focus={result.focus_succeeded} "
                f"error={result.error}"
            )
            return 0 if result.error is None else 1

        # default: start full workspace
        print("Starting default workspace...")
        task = asyncio.create_task(service.start_default_workspace())
        stopper = asyncio.create_task(stop.wait())
        done, _pending = await asyncio.wait(
            {task, stopper}, return_when=asyncio.FIRST_COMPLETED
        )
        if stop.is_set() and not task.done():
            print("Cancelling remaining applications...")
            await service.cancel()
            try:
                await task
            except Exception:
                pass
            print("Cancelled.")
            return 0
        status = await task
        print(f"Workspace finished: {status.status.value}")
        if status.last_run:
            run = status.last_run
            print(
                f"successful={run.successful} failed={run.failed} "
                f"skipped={run.skipped} duration_ms={run.duration_ms}"
            )
            for item in run.applications:
                print(f"  {item.application_id}: {item.result} error={item.error}")
        return 0 if status.status.value in {"READY", "PARTIAL_SUCCESS", "IDLE"} else 1
    finally:
        await service.shutdown()


def main() -> int:
    args = parse_args()
    if not any([args.list, args.status, args.app, args.start]):
        args.start = True
    try:
        return asyncio.run(run(args))
    except KeyboardInterrupt:
        print("\nInterrupted.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
