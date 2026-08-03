"""
Jarvis workspace assistant — double-clap listener entry point.

This step only detects a reliable double clap on the default Windows microphone.
No voice recognition, TTS, dashboard, or cloud APIs.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path


def _check_dependencies() -> None:
    """Fail early with a clear message if required packages are missing."""
    missing: list[str] = []
    for package in ("numpy", "sounddevice"):
        try:
            __import__(package)
        except ImportError:
            missing.append(package)

    if missing:
        names = ", ".join(missing)
        print(
            f"ERROR: Missing Python dependency: {names}\n"
            "Install with: pip install -r requirements.txt",
            file=sys.stderr,
        )
        raise SystemExit(1)


def _setup_logging() -> None:
    """Write important events and errors to logs/jarvis.log."""
    import config

    log_path = Path(__file__).resolve().parent / config.LOG_FILE
    log_path.parent.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8"),
        ],
    )


def main() -> None:
    _check_dependencies()
    _setup_logging()

    # Import after dependency check so ImportError messages stay user-friendly.
    from clap_detector import ClapDetector

    def on_double_clap() -> None:
        # Callback hook for future Jarvis actions (kept minimal for this step).
        print("DOUBLE CLAP CONFIRMED.")

    detector = ClapDetector(on_double_clap=on_double_clap)
    detector.start()


if __name__ == "__main__":
    main()
