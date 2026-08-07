#!/usr/bin/env python3
"""Register Ctrl+Alt+J and wait for SHOW_DASHBOARD (no keylogging)."""

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
from app.core.logging_config import setup_logging
from app.services.hotkeys import GlobalHotkeyService


async def run() -> int:
    base = get_settings()
    settings = Settings(
        **{
            **base.model_dump(),
            "global_hotkey_enabled": True,
            "global_hotkey_show_dashboard": "CTRL+ALT+J",
        }
    )
    setup_logging(settings.log_level)
    triggered = asyncio.Event()

    def on_show() -> None:
        print("SHOW_DASHBOARD TRIGGERED")
        triggered.set()

    service = GlobalHotkeyService(settings, on_show_dashboard=on_show)
    await service.start()
    status = service.get_status()
    print(f"HOTKEY {status.status.value}")
    if status.status.value == "REGISTERED":
        print("HOTKEY REGISTERED")
    print("Press Ctrl+Alt+J (Ctrl+C to stop)")

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
        while not stop.is_set():
            await asyncio.sleep(0.2)
    finally:
        await service.shutdown()
        print("Hotkey unregistered.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
