#!/usr/bin/env python3
"""Development utility: listen for “Wake up, Jarvis.” using production classes.

Examples:
  python tools/test_wake_phrase.py --list-devices
  python tools/test_wake_phrase.py
  python tools/test_wake_phrase.py --device-id 1
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import signal
import sys
from pathlib import Path

# Ensure backend root is on sys.path when launched as a script
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import Settings, get_settings
from app.core.events import VOICE_WAKE_DETECTED, EventBus
from app.core.logging_config import setup_logging
from app.core.state_manager import StateManager
from app.services.voice.audio_devices import AudioDeviceManager
from app.services.voice.voice_service import VoiceService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Test Jarvis offline wake-phrase detection (production VoiceService)."
    )
    parser.add_argument(
        "--list-devices",
        action="store_true",
        help="List input microphones and exit",
    )
    parser.add_argument(
        "--device-id",
        type=int,
        default=None,
        help="Microphone device id for this session",
    )
    return parser.parse_args()


def list_devices() -> int:
    manager = AudioDeviceManager()
    devices = manager.list_input_devices()
    if not devices:
        print("No input microphones found.")
        return 1
    print("Available microphones:")
    for device in devices:
        marker = " (default)" if device.is_default else ""
        print(
            f"  id={device.id}  {device.name}{marker}  "
            f"[{device.host_api}]  rate={device.default_sample_rate}"
        )
    return 0


async def run_listener(device_id: int | None) -> int:
    settings = get_settings()
    setup_logging(settings.log_level)
    logging.getLogger("app").setLevel(logging.INFO)

    if device_id is not None:
        # Session override without mutating the global cached settings object deeply
        settings = Settings(
            **{
                **settings.model_dump(),
                "voice_device_id": device_id,
                "voice_start_automatically": False,
            }
        )

    bus = EventBus()
    state = StateManager(bus)
    service = VoiceService(settings=settings, state_manager=state, event_bus=bus)
    service.set_event_loop(asyncio.get_running_loop())

    async def on_wake(payload: dict) -> None:
        print("\nWAKE PHRASE DETECTED")
        print(f"  phrase={payload.get('phrase')!r}  confidence={payload.get('confidence')}")

    await bus.subscribe(VOICE_WAKE_DETECTED, on_wake)

    print("Initializing voice service…")
    await service.on_startup()
    status = service.get_status()
    print(f"Status: {status.status.value}")
    if status.last_error:
        print(f"Error: {status.last_error}")
        return 1

    if status.status.value != "LISTENING":
        print("Starting listener…")
        status = await service.start()
        print(f"Status: {status.status.value}")
        if status.last_error:
            print(f"Error: {status.last_error}")
            return 1

    mic = status.microphone.name if status.microphone else "unknown"
    print(f"Listening on: {mic}")
    print(f"Say: {settings.wake_phrase}")
    print("Press Ctrl+C to stop.\n")

    stop_event = asyncio.Event()

    def _handle_signal(*_args: object) -> None:
        stop_event.set()

    try:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, _handle_signal)
            except NotImplementedError:
                # Windows typically lacks add_signal_handler for these
                signal.signal(sig, lambda *_: stop_event.set())
    except Exception:
        pass

    try:
        await stop_event.wait()
    except asyncio.CancelledError:
        pass
    finally:
        print("\nStopping…")
        await service.shutdown()
        print("Stopped.")
    return 0


def main() -> int:
    args = parse_args()
    if args.list_devices:
        return list_devices()
    try:
        return asyncio.run(run_listener(args.device_id))
    except KeyboardInterrupt:
        print("\nInterrupted.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
