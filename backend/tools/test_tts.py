#!/usr/bin/env python3
"""Development utility: test Piper TTS using production classes.

Examples:
  python tools/test_tts.py --list-devices
  python tools/test_tts.py --welcome
  python tools/test_tts.py --line 1
  python tools/test_tts.py --device-id 4 --welcome
"""

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
from app.services.tts.audio_output_devices import AudioOutputDeviceManager
from app.services.tts.piper_engine import PiperEngine, PiperEngineError
from app.services.tts.tts_service import TtsService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Test Jarvis offline Piper TTS.")
    parser.add_argument("--list-devices", action="store_true")
    parser.add_argument("--device-id", type=int, default=None)
    parser.add_argument("--welcome", action="store_true", help="Play full welcome sequence")
    parser.add_argument("--line", type=int, choices=[1, 2, 3], default=None)
    return parser.parse_args()


def list_devices() -> int:
    devices = AudioOutputDeviceManager().list_output_devices()
    if not devices:
        print("No output devices found.")
        return 1
    print("Available output devices:")
    for device in devices:
        marker = " (default)" if device.is_default else ""
        print(f"  id={device.id}  {device.name}{marker}  [{device.host_api}]")
    return 0


async def run(args: argparse.Namespace) -> int:
    settings = get_settings()
    setup_logging(settings.log_level)
    if args.device_id is not None:
        settings = Settings(
            **{**settings.model_dump(), "tts_output_device_id": args.device_id}
        )

    bus = EventBus()
    service = TtsService(settings=settings, event_bus=bus)
    service.bind(event_bus=bus, loop=asyncio.get_running_loop())

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
        await service.on_startup()
        status = service.get_status()
        if status.status.value in {"ENGINE_MISSING", "MODEL_MISSING", "ERROR", "OUTPUT_UNAVAILABLE"}:
            print(f"TTS not ready: {status.status.value}")
            if status.last_error:
                print(status.last_error)
            return 1

        print("Piper engine ready.")
        print(f"Voice model loaded: {status.voice}")
        out = status.output_device.name if status.output_device else "unknown"
        print(f"Output device: {out}")

        if args.line is not None:
            line = settings.welcome_lines()[args.line - 1]
            print(f"Speaking line {args.line} of 3...")
            engine = service._engine  # reuse validated engine
            audio = await asyncio.to_thread(engine.synthesize, line)
            await asyncio.to_thread(
                service._player.play,
                audio,
                device_id=status.output_device.id if status.output_device else None,
            )
            print("Done.")
            return 0

        if args.welcome or args.line is None:
            # Default action when not listing: welcome sequence
            print("Speaking line 1 of 3...")
            task = asyncio.create_task(service.speak_welcome_sequence())
            done, _ = await asyncio.wait(
                [task, asyncio.create_task(stop.wait())],
                return_when=asyncio.FIRST_COMPLETED,
            )
            if stop.is_set():
                print("Cancelling...")
                await service.cancel()
                return 0
            await task
            print("Welcome sequence complete.")
        return 0
    except PiperEngineError as exc:
        print(f"Error: {exc.user_message}")
        return 1
    except KeyboardInterrupt:
        print("\nInterrupted.")
        await service.cancel()
        return 0
    finally:
        await service.shutdown()


def main() -> int:
    args = parse_args()
    if args.list_devices:
        return list_devices()
    if not args.welcome and args.line is None:
        args.welcome = True
    try:
        return asyncio.run(run(args))
    except KeyboardInterrupt:
        print("\nInterrupted.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
