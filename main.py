"""
Jarvis workspace assistant — double-clap + offline wake-phrase entry point.

Flow:
  LISTENING_FOR_CLAPS
    → DOUBLE_CLAP_DETECTED
    → LISTENING_FOR_WAKE_PHRASE
    → JARVIS_ACTIVATED  (or timeout / mismatch)
    → RETURNING_TO_CLAP_MODE

No TTS, dashboard, app launching, or cloud APIs in this step.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path


def _check_dependencies() -> None:
    """Fail early with a clear message if required packages are missing."""
    missing: list[str] = []
    for package in ("numpy", "sounddevice", "vosk"):
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

    import config
    from clap_detector import ClapDetector
    from wake_word_listener import WakeWordListener, validate_vosk_model_path

    logger = logging.getLogger("jarvis.main")

    # Validate and load the Vosk model once at startup (not on every clap).
    try:
        validate_vosk_model_path(config.VOSK_MODEL_PATH)
        wake_listener = WakeWordListener()
    except (FileNotFoundError, NotADirectoryError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        logger.error("%s", exc)
        raise SystemExit(1) from exc

    state = "LISTENING_FOR_CLAPS"
    logger.info("State: %s", state)

    def on_double_clap() -> None:
        print("DOUBLE CLAP CONFIRMED.")

    def on_after_double_clap() -> None:
        """
        Runs on the clap detector's main loop after the clap mic is paused.

        Mic ownership at this point:
          - clap InputStream is closed
          - wake RawInputStream may open exclusively
          - wake stream is closed before this returns
          - clap detector then resumes its InputStream
        """
        nonlocal state
        state = "LISTENING_FOR_WAKE_PHRASE"
        print("Listening for wake phrase...")
        logger.info("State: %s", state)

        try:
            result = wake_listener.listen_for_wake_phrase()
        except (PermissionError, RuntimeError) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            logger.exception("Wake-phrase listening failed.")
            state = "RETURNING_TO_CLAP_MODE"
            return

        if result.matched:
            print(f"Heard: {result.text}")
            print("WAKE PHRASE CONFIRMED.")
            print("Jarvis activated.")
            state = "JARVIS_ACTIVATED"
            logger.info("State: %s (heard=%r)", state, result.text)
        elif result.timed_out and not result.text:
            print("Wake phrase timeout.")
            logger.info("Wake phrase timeout.")
            state = "RETURNING_TO_CLAP_MODE"
        elif result.text:
            print(f"Heard: {result.text}")
            print("Wake phrase not matched.")
            logger.info("Wake phrase not matched (heard=%r)", result.text)
            state = "RETURNING_TO_CLAP_MODE"
        else:
            print("Wake phrase timeout.")
            logger.info("Wake phrase timeout (empty recognition).")
            state = "RETURNING_TO_CLAP_MODE"

    detector = ClapDetector(
        on_double_clap=on_double_clap,
        on_after_double_clap=on_after_double_clap,
    )

    try:
        detector.start()
    finally:
        wake_listener.close()


if __name__ == "__main__":
    main()
