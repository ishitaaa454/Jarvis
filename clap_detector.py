"""
Reusable double-clap detector using the default Windows microphone.

Detection idea:
  1. Calibrate ambient peak levels for a few seconds.
  2. Track loud peaks above threshold.
  3. On the falling edge, accept the event as a clap only if it was
     short and somewhat impulsive (crest + high-frequency checks).
  4. Confirm a double clap when two claps fall inside the timing window.

Laptop mics often compress/filter audio, so crest/HF gates are kept modest.
Enable config.DEBUG_NEAR_MISSES to see why loud sounds were rejected.
"""

from __future__ import annotations

import logging
import sys
import time
from collections import deque
from collections.abc import Callable
from typing import Optional

import numpy as np

import config

try:
    import sounddevice as sd
except ImportError as exc:  # pragma: no cover - environment dependent
    raise ImportError(
        "Missing dependency 'sounddevice'. Install with: pip install -r requirements.txt"
    ) from exc


logger = logging.getLogger("jarvis.clap")


def _block_features(samples: np.ndarray) -> tuple[float, float, float, float]:
    """Return (peak, rms, crest, hf_ratio) for one audio block."""
    peak = float(np.max(np.abs(samples)))
    rms = float(np.sqrt(np.mean(np.square(samples)))) + 1e-8
    crest = peak / rms
    if samples.size > 1:
        hf = float(np.sqrt(np.mean(np.square(np.diff(samples)))))
    else:
        hf = 0.0
    return peak, rms, crest, hf / rms


class ClapDetector:
    """Listen to the default mic and invoke a callback on double-clap events."""

    def __init__(
        self,
        on_double_clap: Optional[Callable[[], None]] = None,
        on_after_double_clap: Optional[Callable[[], None]] = None,
        sample_rate: int = config.SAMPLE_RATE,
        block_size: int = config.BLOCK_SIZE,
        calibration_duration: float = config.CALIBRATION_DURATION,
        threshold_multiplier: float = config.THRESHOLD_MULTIPLIER,
        min_threshold: float = config.MIN_THRESHOLD,
        max_threshold: float = config.MAX_THRESHOLD,
        min_clap_interval: float = config.MIN_CLAP_INTERVAL,
        max_clap_interval: float = config.MAX_CLAP_INTERVAL,
        cooldown_duration: float = config.COOLDOWN_DURATION,
        max_clap_duration: float = config.MAX_CLAP_DURATION,
        clap_refractory: float = config.CLAP_REFRACTORY,
        min_rise_ratio: float = config.MIN_RISE_RATIO,
        min_crest_factor: float = config.MIN_CREST_FACTOR,
        min_hf_ratio: float = config.MIN_HF_RATIO,
        debug_near_misses: bool = config.DEBUG_NEAR_MISSES,
    ) -> None:
        self.on_double_clap = on_double_clap
        # Called on the main listener loop (NOT the PortAudio callback thread)
        # after the clap mic has been paused — use this for wake-phrase listening.
        self.on_after_double_clap = on_after_double_clap
        self.sample_rate = sample_rate
        self.block_size = block_size
        self.calibration_duration = calibration_duration
        self.threshold_multiplier = threshold_multiplier
        self.min_threshold = min_threshold
        self.max_threshold = max_threshold
        self.min_clap_interval = min_clap_interval
        self.max_clap_interval = max_clap_interval
        self.cooldown_duration = cooldown_duration
        self.max_clap_duration = max_clap_duration
        self.clap_refractory = clap_refractory
        self.min_rise_ratio = min_rise_ratio
        self.min_crest_factor = min_crest_factor
        self.min_hf_ratio = min_hf_ratio
        self.debug_near_misses = debug_near_misses

        self.threshold: float = min_threshold
        self._running = False
        self._stream: Optional[sd.InputStream] = None
        self._paused = False
        self._handoff_requested = False

        self._calibrating = False
        self._calibration_peaks: list[float] = []
        self._calibration_start: float = 0.0

        history_blocks = max(4, int(0.25 * sample_rate / max(block_size, 1)))
        self._recent_peaks: deque[float] = deque(maxlen=history_blocks)

        self._above_threshold = False
        self._peak_start: float = 0.0
        self._peak_max: float = 0.0
        self._best_crest: float = 0.0
        self._best_hf: float = 0.0
        self._last_clap_time: Optional[float] = None
        self._awaiting_second = False
        self._cooldown_until: float = 0.0
        self._refractory_until: float = 0.0
        self._last_debug_print: float = 0.0

    def start(self) -> None:
        """Open the microphone, calibrate, then listen until stop() or Ctrl+C."""
        self._ensure_microphone_available()

        print("Jarvis listener started.")
        logger.info("Jarvis listener started.")

        print("Calibrating microphone...")
        logger.info("Starting microphone calibration (%.1fs).", self.calibration_duration)

        self._calibrating = True
        self._calibration_peaks = []
        self._calibration_start = time.monotonic()
        self._running = True

        try:
            self._stream = sd.InputStream(
                samplerate=self.sample_rate,
                blocksize=self.block_size,
                channels=1,
                dtype="float32",
                callback=self._audio_callback,
            )
            self._stream.start()
        except PermissionError as exc:
            self._fail(
                "Microphone permission denied. Allow mic access in "
                "Windows Settings > Privacy & security > Microphone.",
                exc,
            )
        except Exception as exc:  # noqa: BLE001
            self._fail(f"Audio stream failure: {exc}", exc)

        try:
            while self._running:
                time.sleep(0.1)
                if self._awaiting_second and self._last_clap_time is not None:
                    if (time.monotonic() - self._last_clap_time) > self.max_clap_interval:
                        logger.debug("Double-clap window expired; resetting.")
                        self._awaiting_second = False
                        self._last_clap_time = None

                # Microphone handoff runs on this loop (not the audio callback).
                if self._handoff_requested:
                    self._handoff_requested = False
                    self._run_post_clap_handoff()
        except KeyboardInterrupt:
            print("\nStopping Jarvis listener...")
            logger.info("Interrupted by user (Ctrl+C).")
        finally:
            self.stop()

    def pause_microphone(self) -> None:
        """
        Release the mic so another listener (wake phrase) can open it.

        Clap analysis is suspended until resume_microphone().
        """
        if self._stream is None:
            self._paused = True
            return
        try:
            self._stream.stop()
            self._stream.close()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Error while pausing clap microphone: %s", exc)
        self._stream = None
        self._paused = True
        # Reset in-flight clap state so resume starts clean.
        self._above_threshold = False
        self._awaiting_second = False
        self._last_clap_time = None
        self._recent_peaks.clear()
        logger.info("Clap microphone paused (released for wake-phrase listening).")

    def resume_microphone(self) -> None:
        """Re-open the clap mic after the wake listener has closed its stream."""
        if not self._running:
            return
        if self._stream is not None:
            self._paused = False
            return
        try:
            self._stream = sd.InputStream(
                samplerate=self.sample_rate,
                blocksize=self.block_size,
                channels=1,
                dtype="float32",
                callback=self._audio_callback,
            )
            self._stream.start()
            self._paused = False
            # Brief cooldown after wake cycle so residual speech is not a clap.
            self._cooldown_until = time.monotonic() + self.cooldown_duration
            logger.info("Clap microphone resumed.")
        except Exception as exc:  # noqa: BLE001
            self._fail(f"Audio stream failure while resuming clap detection: {exc}", exc)

    def _run_post_clap_handoff(self) -> None:
        """Pause clap mic → run wake handler → resume clap mic."""
        # --- MIC HANDOFF: clap detector releases the device first ---
        self.pause_microphone()
        try:
            if self.on_after_double_clap is not None:
                self.on_after_double_clap()
        except Exception:  # noqa: BLE001
            logger.exception("Error in on_after_double_clap callback.")
        finally:
            # --- MIC HANDOFF: clap detector reclaims the device ---
            if self._running:
                self.resume_microphone()
                print("Returning to clap detection.")
                logger.info("State: RETURNING_TO_CLAP_MODE")

    def stop(self) -> None:
        self._running = False
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception as exc:  # noqa: BLE001
                logger.warning("Error while closing audio stream: %s", exc)
            self._stream = None
        self._paused = False
        logger.info("Jarvis listener stopped.")

    def _ensure_microphone_available(self) -> None:
        try:
            devices = sd.query_devices()
            default_input = sd.default.device[0]
        except Exception as exc:  # noqa: BLE001
            self._fail(f"Unable to query audio devices: {exc}", exc)
            return

        has_input = False
        for i in range(len(devices)):
            try:
                if sd.query_devices(i)["max_input_channels"] > 0:
                    has_input = True
                    break
            except Exception:  # noqa: BLE001
                continue

        if not has_input:
            self._fail("No microphone found. Connect a mic or enable the laptop microphone.")

        if default_input is None or default_input < 0:
            self._fail("No default microphone is configured in Windows sound settings.")

    def _fail(self, message: str, exc: Optional[BaseException] = None) -> None:
        print(f"ERROR: {message}", file=sys.stderr)
        if exc is not None:
            logger.exception(message)
        else:
            logger.error(message)
        raise SystemExit(1) from exc

    def _audio_callback(
        self,
        indata: np.ndarray,
        frames: int,
        time_info: object,
        status: sd.CallbackFlags,
    ) -> None:
        if status:
            logger.warning("Audio stream status: %s", status)

        if self._paused or self._handoff_requested:
            return

        samples = indata[:, 0] if indata.ndim > 1 else indata.flatten()
        peak, _rms, crest, hf_ratio = _block_features(samples)
        now = time.monotonic()

        if self._calibrating:
            self._handle_calibration(peak, now)
            return

        if now < self._cooldown_until:
            self._above_threshold = False
            self._recent_peaks.append(peak)
            return

        if now < self._refractory_until:
            self._recent_peaks.append(peak)
            return

        self._process_features(peak, crest, hf_ratio, now)

    def _handle_calibration(self, peak: float, now: float) -> None:
        self._calibration_peaks.append(peak)
        if (now - self._calibration_start) < self.calibration_duration:
            return

        peaks = np.asarray(self._calibration_peaks, dtype=np.float64)
        ambient_median = float(np.median(peaks)) if peaks.size else 0.0
        ambient_p75 = float(np.percentile(peaks, 75)) if peaks.size else 0.0
        # Use quiet-room level only. A high p95 usually means noise/talking
        # during calibration and must not push the threshold above real claps.
        ambient = ambient_median if ambient_median > 0 else ambient_p75

        raw_threshold = ambient * self.threshold_multiplier
        self.threshold = min(self.max_threshold, max(self.min_threshold, raw_threshold))
        self._calibrating = False
        self._recent_peaks.clear()

        print("Calibration complete.")
        print(f"  Background peak (median): {ambient_median:.5f}")
        print(f"  Clap threshold:           {self.threshold:.5f}")
        print("  Tip: stay silent during calibration.")
        if self.debug_near_misses:
            print("  Debug near-misses: ON (clap once — watch for [near-miss] lines)")
        print("Listening for double clap...")
        logger.info(
            "Calibration complete. ambient_median=%.5f ambient_p75=%.5f threshold=%.5f",
            ambient_median,
            ambient_p75,
            self.threshold,
        )

    def _debug(self, message: str, now: float) -> None:
        if not self.debug_near_misses:
            return
        # Rate-limit so we never spam the console with raw continuous levels.
        if (now - self._last_debug_print) < 0.35:
            return
        self._last_debug_print = now
        print(f"[near-miss] {message}")
        logger.info("near-miss: %s", message)

    def _process_features(self, peak: float, crest: float, hf_ratio: float, now: float) -> None:
        baseline = float(np.median(self._recent_peaks)) if self._recent_peaks else 0.0
        self._recent_peaks.append(peak)

        # Enter / continue a loud peak based on amplitude only.
        # Crest/HF are judged on the falling edge using the best values seen.
        if peak >= self.threshold:
            if not self._above_threshold:
                # After the first clap the mic level is often still high, so a
                # strict rise check rejects real second claps (seen as 0.8–1.0x).
                if not self._awaiting_second:
                    rise = peak / max(baseline, 1e-6) if baseline > 0 else float("inf")
                    if rise < self.min_rise_ratio:
                        self._debug(
                            f"peak={peak:.3f} but soft rise {rise:.1f}x "
                            f"(need {self.min_rise_ratio:.1f}x)",
                            now,
                        )
                        return
                self._above_threshold = True
                self._peak_start = now
                self._peak_max = peak
                self._best_crest = crest
                self._best_hf = hf_ratio
            else:
                self._peak_max = max(self._peak_max, peak)
                self._best_crest = max(self._best_crest, crest)
                self._best_hf = max(self._best_hf, hf_ratio)
            return

        # Below threshold but somewhat loud — useful while tuning.
        if peak >= self.threshold * 0.55:
            self._debug(
                f"peak={peak:.3f} below threshold={self.threshold:.3f} "
                f"(crest={crest:.1f} hf={hf_ratio:.2f})",
                now,
            )

        if not self._above_threshold:
            return

        self._above_threshold = False
        duration = now - self._peak_start

        if duration > self.max_clap_duration:
            self._debug(
                f"rejected long peak={self._peak_max:.3f} duration={duration:.3f}s",
                now,
            )
            return

        if self._best_crest < self.min_crest_factor:
            self._debug(
                f"rejected peak={self._peak_max:.3f} crest={self._best_crest:.1f} "
                f"(need {self.min_crest_factor:.1f})",
                now,
            )
            return

        if self._best_hf < self.min_hf_ratio:
            self._debug(
                f"rejected peak={self._peak_max:.3f} hf={self._best_hf:.2f} "
                f"(need {self.min_hf_ratio:.2f})",
                now,
            )
            return

        self._on_clap(now)

    def _on_clap(self, now: float) -> None:
        self._refractory_until = now + self.clap_refractory
        # Clear recent peaks so the second clap is not rejected as a "soft rise"
        # against the still-elevated energy from the first clap.
        self._recent_peaks.clear()

        if not self._awaiting_second or self._last_clap_time is None:
            self._last_clap_time = now
            self._awaiting_second = True
            print("First clap detected.")
            logger.info("First clap detected.")
            return

        interval = now - self._last_clap_time

        if interval < self.min_clap_interval:
            logger.debug("Ignored clap too soon (%.3fs).", interval)
            return

        if interval > self.max_clap_interval:
            self._last_clap_time = now
            self._awaiting_second = True
            print("First clap detected.")
            logger.info("First clap detected (previous window expired).")
            return

        print("Second clap detected.")
        logger.info("Second clap detected (interval=%.3fs).", interval)

        self._awaiting_second = False
        self._last_clap_time = None

        logger.info("DOUBLE CLAP CONFIRMED.")

        if self.on_double_clap is not None:
            try:
                self.on_double_clap()
            except Exception:  # noqa: BLE001
                logger.exception("Error in on_double_clap callback.")
        else:
            print("DOUBLE CLAP CONFIRMED.")

        if self.on_after_double_clap is not None:
            # Defer cooldown / wake work to the main loop after mic pause.
            self._cooldown_until = 0.0
            self._handoff_requested = True
            logger.info("State: DOUBLE_CLAP_DETECTED (handoff requested)")
        else:
            self._cooldown_until = now + self.cooldown_duration
            print("Cooldown active...")
