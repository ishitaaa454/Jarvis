"""Offline wake-phrase VoiceService owning the microphone and recognition worker."""

from __future__ import annotations

import asyncio
import logging
import queue
import threading
from typing import Any, Callable

import numpy as np

from app.core.config import Settings, get_settings
from app.core.events import (
    VOICE_ERROR,
    VOICE_STATUS_CHANGED,
    VOICE_WAKE_DETECTED,
    EventBus,
)
from app.core.state_manager import StateManager
from app.models.assistant_state import AssistantState
from app.models.voice import (
    AudioDeviceInfo,
    MicrophoneStatus,
    VoiceServiceStatus,
    VoiceStatusResponse,
    voice_status_to_ws_payload,
)
from app.services.voice.audio_devices import AudioDeviceError, AudioDeviceManager
from app.services.voice.wake_phrase_detector import (
    VoskModelMissingError,
    WakePhraseDetector,
)
from app.utils.time_utils import utc_now

logger = logging.getLogger(__name__)

# Sentinel to stop the recognition worker cleanly
_STOP = object()


class VoiceService:
    """Coordinates microphone capture, wake detection, StateManager, and events.

    Phase 2 does not implement TTS. ``speak`` remains unimplemented until Phase 3.
    Only one microphone stream is opened at a time.
    """

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        state_manager: StateManager | None = None,
        event_bus: EventBus | None = None,
        device_manager: AudioDeviceManager | None = None,
        detector: WakePhraseDetector | None = None,
        stream_factory: Callable[..., Any] | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._state_manager = state_manager
        self._event_bus = event_bus
        self._device_manager = device_manager or AudioDeviceManager()
        self._detector = detector or WakePhraseDetector(
            self._settings.resolved_vosk_model_path(),
            wake_phrase=self._settings.wake_phrase,
            confidence_threshold=self._settings.wake_confidence_threshold,
            cooldown_seconds=self._settings.wake_cooldown_seconds,
            debug_transcripts=self._settings.voice_debug_transcripts,
        )
        self._stream_factory = stream_factory

        self._status = (
            VoiceServiceStatus.DISABLED
            if not self._settings.voice_enabled
            else VoiceServiceStatus.STOPPED
        )
        self._loop: asyncio.AbstractEventLoop | None = None
        self._audio_queue: queue.Queue[Any] = queue.Queue(
            maxsize=self._settings.voice_audio_queue_size
        )
        self._worker: threading.Thread | None = None
        self._stream: Any | None = None
        self._stop_event = threading.Event()
        self._lock = asyncio.Lock()
        self._selected_device: AudioDeviceInfo | None = None
        self._active_sample_rate: int = self._settings.voice_sample_rate
        self._last_activation_at = None
        self._last_error: str | None = None
        self._model_loaded = False
        self._activation_generation = 0
        self._return_listening_task: asyncio.Task[None] | None = None
        self._queue_overflows = 0
        self._accepting_actions = True

    # ------------------------------------------------------------------
    # Public status / device helpers
    # ------------------------------------------------------------------

    def bind(
        self,
        *,
        state_manager: StateManager,
        event_bus: EventBus,
        loop: asyncio.AbstractEventLoop | None = None,
    ) -> None:
        """Attach FastAPI runtime dependencies after construction."""
        self._state_manager = state_manager
        self._event_bus = event_bus
        if loop is not None:
            self._loop = loop

    def set_event_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def speak(self, text: str) -> None:
        """Reserved for Phase 3 British-male TTS."""
        raise NotImplementedError(
            f"Text-to-speech is not available in Phase 2 (text={text!r})."
        )

    def get_status(self) -> VoiceStatusResponse:
        mic = None
        if self._selected_device is not None:
            mic = MicrophoneStatus(
                id=self._selected_device.id,
                name=self._selected_device.name,
                is_default=self._selected_device.is_default,
            )
        return VoiceStatusResponse(
            enabled=self._settings.voice_enabled,
            status=self._status,
            wake_phrase=self._settings.wake_phrase,
            model_loaded=self._model_loaded,
            model_path=self._settings.public_model_path(),
            microphone=mic,
            last_activation_at=self._last_activation_at,
            last_error=self._last_error,
        )

    def list_devices(self) -> list[AudioDeviceInfo]:
        return self._device_manager.list_input_devices()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> VoiceStatusResponse:
        """Start listening. Idempotent if already listening."""
        async with self._lock:
            if not self._accepting_actions:
                return self.get_status()

            if not self._settings.voice_enabled:
                self._status = VoiceServiceStatus.DISABLED
                self._last_error = "Voice service is disabled by configuration."
                await self._publish_status()
                return self.get_status()

            if self._status == VoiceServiceStatus.LISTENING and self._stream is not None:
                return self.get_status()

            if self._status == VoiceServiceStatus.STARTING:
                return self.get_status()

            await self._start_locked()
            return self.get_status()

    async def stop(self) -> VoiceStatusResponse:
        """Stop listening. Idempotent if already stopped."""
        async with self._lock:
            await self._stop_locked(reason="manual")
            return self.get_status()

    async def shutdown(self) -> None:
        """FastAPI shutdown path — stop accepting actions and release resources."""
        self._accepting_actions = False
        async with self._lock:
            await self._stop_locked(reason="shutdown")
        self._detector.release()
        logger.info("Voice service shutdown complete")

    async def set_device(self, device_id: int) -> VoiceStatusResponse:
        """Validate device, swap microphone, restart if previously listening."""
        async with self._lock:
            was_listening = self._status == VoiceServiceStatus.LISTENING
            try:
                device = self._device_manager.get_device(device_id)
            except AudioDeviceError as exc:
                self._last_error = exc.user_message
                await self._publish_error(exc.code, exc.user_message)
                raise

            logger.info("Changing voice input device to id=%s name=%r", device.id, device.name)
            await self._stop_locked(reason="device_change", restore_idle=False)
            self._selected_device = device
            self._last_error = None

            if was_listening and self._accepting_actions:
                await self._start_locked()
            else:
                await self._publish_status()

            return self.get_status()

    async def simulate_wake(
        self,
        *,
        phrase: str | None = None,
        confidence: float = 0.99,
    ) -> VoiceStatusResponse:
        """Development-only wake activation without microphone audio."""
        text = phrase or self._settings.wake_phrase
        self._detector.reset_cooldown()
        outcome = self._detector.evaluate_recognized_text(text, confidence=confidence)
        if outcome.activated:
            await self._handle_activation(outcome.phrase or "wake up jarvis", outcome.confidence)
        else:
            # Explicit test endpoint still drives dashboard / WebSocket verification
            await self._handle_activation("wake up jarvis", confidence)
        return self.get_status()

    async def on_startup(self) -> None:
        """Called from FastAPI lifespan after the event loop is running."""
        self._loop = asyncio.get_running_loop()
        logger.info("Voice service initializing (enabled=%s)", self._settings.voice_enabled)

        if not self._settings.voice_enabled:
            self._status = VoiceServiceStatus.DISABLED
            await self._publish_status()
            return

        # Probe model once without crashing the app
        try:
            self._status = VoiceServiceStatus.LOADING_MODEL
            await self._publish_status()
            self._detector.ensure_model_loaded()
            self._model_loaded = True
            self._last_error = None
        except VoskModelMissingError as exc:
            self._model_loaded = False
            self._status = VoiceServiceStatus.MODEL_MISSING
            self._last_error = str(exc)
            logger.error("Voice model unavailable: %s", exc)
            await self._publish_error("MODEL_MISSING", str(exc))
            await self._publish_status()
            return
        except Exception as exc:
            self._model_loaded = False
            self._status = VoiceServiceStatus.ERROR
            self._last_error = f"Model load failed: {exc}"
            logger.exception("Unexpected model load failure")
            await self._publish_error("MODEL_LOAD_FAILED", self._last_error)
            await self._publish_status()
            return

        # Resolve default / configured microphone without starting yet
        try:
            self._selected_device = self._device_manager.resolve_device(
                self._settings.voice_device_id,
                self._settings.voice_device_name or None,
            )
        except AudioDeviceError as exc:
            self._status = VoiceServiceStatus.ERROR
            self._last_error = exc.user_message
            await self._publish_error(exc.code, exc.user_message)
            await self._publish_status()
            return

        if self._selected_device is None:
            self._status = VoiceServiceStatus.ERROR
            self._last_error = "No microphone input devices are available."
            await self._publish_error("NO_MICROPHONE", self._last_error)
            await self._publish_status()
            return

        self._status = VoiceServiceStatus.STOPPED
        await self._publish_status()

        if self._settings.voice_start_automatically:
            await self.start()

    # ------------------------------------------------------------------
    # Internal start / stop
    # ------------------------------------------------------------------

    async def _start_locked(self) -> None:
        self._status = VoiceServiceStatus.STARTING
        await self._publish_status()

        try:
            if not self._model_loaded:
                self._status = VoiceServiceStatus.LOADING_MODEL
                await self._publish_status()
                self._detector.ensure_model_loaded()
                self._model_loaded = True

            if self._selected_device is None:
                self._selected_device = self._device_manager.resolve_device(
                    self._settings.voice_device_id,
                    self._settings.voice_device_name or None,
                )
            if self._selected_device is None:
                raise AudioDeviceError(
                    "No microphone input devices are available.",
                    code="NO_MICROPHONE",
                )

            sample_rate = self._open_stream(self._selected_device)
            self._active_sample_rate = sample_rate
            self._detector.prepare_recognizer(sample_rate)

            self._clear_queue()
            self._stop_event.clear()
            self._worker = threading.Thread(
                target=self._recognition_worker,
                name="jarvis-wake-recognizer",
                daemon=True,
            )
            self._worker.start()

            self._status = VoiceServiceStatus.LISTENING
            self._last_error = None
            logger.info(
                "Wake listener started on device id=%s name=%r rate=%s",
                self._selected_device.id,
                self._selected_device.name,
                sample_rate,
            )
            await self._publish_status()

            if self._state_manager is not None:
                await self._state_manager.set_state(AssistantState.LISTENING)

        except VoskModelMissingError as exc:
            self._model_loaded = False
            self._status = VoiceServiceStatus.MODEL_MISSING
            self._last_error = str(exc)
            await self._teardown_stream_and_worker()
            await self._publish_error("MODEL_MISSING", str(exc))
            await self._publish_status()
        except AudioDeviceError as exc:
            self._status = VoiceServiceStatus.ERROR
            self._last_error = exc.user_message
            await self._teardown_stream_and_worker()
            await self._publish_error(exc.code, exc.user_message)
            await self._publish_status()
        except Exception as exc:
            self._status = VoiceServiceStatus.ERROR
            self._last_error = f"Failed to start wake listener: {exc}"
            logger.exception("Failed to start wake listener")
            await self._teardown_stream_and_worker()
            await self._publish_error("START_FAILED", self._last_error)
            await self._publish_status()

    async def _stop_locked(self, *, reason: str, restore_idle: bool = True) -> None:
        if self._status in {
            VoiceServiceStatus.STOPPED,
            VoiceServiceStatus.DISABLED,
            VoiceServiceStatus.MODEL_MISSING,
        } and self._stream is None and self._worker is None:
            # Idempotent no-op
            if self._status not in {
                VoiceServiceStatus.DISABLED,
                VoiceServiceStatus.MODEL_MISSING,
                VoiceServiceStatus.ERROR,
            }:
                self._status = VoiceServiceStatus.STOPPED
            return

        previous = self._status
        self._status = VoiceServiceStatus.STOPPING
        if previous != VoiceServiceStatus.STOPPING:
            await self._publish_status()

        await self._teardown_stream_and_worker()

        if self._status != VoiceServiceStatus.DISABLED:
            self._status = VoiceServiceStatus.STOPPED

        logger.info("Wake listener stopped (reason=%s)", reason)
        await self._publish_status()

        if (
            restore_idle
            and reason == "manual"
            and self._state_manager is not None
        ):
            try:
                current = self._state_manager.current_state
                if current in {AssistantState.LISTENING, AssistantState.PROCESSING}:
                    await self._state_manager.set_state(AssistantState.IDLE)
            except Exception:
                logger.exception("Failed to restore assistant state after voice stop")

    async def _teardown_stream_and_worker(self) -> None:
        self._stop_event.set()
        try:
            self._audio_queue.put_nowait(_STOP)
        except queue.Full:
            try:
                self._audio_queue.get_nowait()
            except queue.Empty:
                pass
            try:
                self._audio_queue.put_nowait(_STOP)
            except queue.Full:
                pass

        if self._stream is not None:
            try:
                self._stream.stop()
            except Exception:
                logger.exception("Error stopping audio stream")
            try:
                self._stream.close()
            except Exception:
                logger.exception("Error closing audio stream")
            self._stream = None

        worker = self._worker
        self._worker = None
        if worker is not None and worker.is_alive():
            await asyncio.to_thread(worker.join, 3.0)
            if worker.is_alive():
                logger.warning("Recognition worker did not exit within timeout")

        self._clear_queue()
        self._detector.release()

    def _clear_queue(self) -> None:
        while True:
            try:
                self._audio_queue.get_nowait()
            except queue.Empty:
                break

    # ------------------------------------------------------------------
    # Audio stream
    # ------------------------------------------------------------------

    def _open_stream(self, device: AudioDeviceInfo) -> int:
        """Open a mono PCM stream. Prefer 16 kHz; resample if needed."""
        target_rate = self._settings.voice_sample_rate
        block_size = self._settings.voice_block_size

        def callback(indata: np.ndarray, frames: int, time_info: Any, status: Any) -> None:
            if status:
                logger.warning("Audio stream status: %s", status)
            if self._stop_event.is_set():
                return
            # Minimal callback work: copy and enqueue
            pcm = self._frames_to_pcm16(indata, device_rate=self._callback_rate, target_rate=target_rate)
            try:
                self._audio_queue.put_nowait(pcm)
            except queue.Full:
                self._queue_overflows += 1
                if self._queue_overflows == 1 or self._queue_overflows % 25 == 0:
                    logger.warning(
                        "Audio queue full — dropping frames (overflows=%s)",
                        self._queue_overflows,
                    )
                try:
                    self._audio_queue.get_nowait()
                except queue.Empty:
                    pass
                try:
                    self._audio_queue.put_nowait(pcm)
                except queue.Full:
                    pass

        # Prefer requesting 16 kHz directly
        open_rate = target_rate
        self._callback_rate = target_rate

        factory = self._stream_factory
        if factory is None:
            try:
                import sounddevice as sd
            except ImportError as exc:
                raise AudioDeviceError(
                    "sounddevice is not installed. Install backend requirements.",
                    code="SOUNDDEVICE_MISSING",
                ) from exc

            def factory(**kwargs: Any) -> Any:
                return sd.InputStream(**kwargs)

        try:
            stream = factory(
                samplerate=open_rate,
                blocksize=block_size,
                device=device.id,
                channels=1,
                dtype="float32",
                callback=callback,
            )
            stream.start()
            self._stream = stream
            logger.info("Opened microphone stream at %s Hz (device=%s)", open_rate, device.id)
            return open_rate
        except Exception as primary_exc:
            logger.warning(
                "Could not open device %s at %s Hz (%s); trying native rate",
                device.id,
                open_rate,
                primary_exc,
            )
            native = int(device.default_sample_rate) or target_rate
            if native == open_rate:
                raise AudioDeviceError(
                    f"Microphone '{device.name}' rejected sample rate {open_rate} Hz.",
                    code="UNSUPPORTED_SAMPLE_RATE",
                ) from primary_exc

            self._callback_rate = native
            try:
                stream = factory(
                    samplerate=native,
                    blocksize=max(1, int(block_size * native / target_rate)),
                    device=device.id,
                    channels=1,
                    dtype="float32",
                    callback=callback,
                )
                stream.start()
                self._stream = stream
                logger.info(
                    "Opened microphone at native %s Hz with resampling to %s Hz",
                    native,
                    target_rate,
                )
                return target_rate
            except Exception as exc:
                raise AudioDeviceError(
                    f"Unable to open microphone '{device.name}': {exc}",
                    code="MICROPHONE_OPEN_FAILED",
                ) from exc

    @staticmethod
    def _frames_to_pcm16(
        indata: np.ndarray,
        *,
        device_rate: int,
        target_rate: int,
    ) -> bytes:
        mono = np.asarray(indata[:, 0] if indata.ndim > 1 else indata, dtype=np.float32)
        if device_rate != target_rate and len(mono) > 1:
            mono = _resample_linear(mono, device_rate, target_rate)
        clipped = np.clip(mono, -1.0, 1.0)
        pcm = (clipped * 32767.0).astype(np.int16)
        return pcm.tobytes()

    # ------------------------------------------------------------------
    # Recognition worker (background thread)
    # ------------------------------------------------------------------

    def _recognition_worker(self) -> None:
        logger.info("Recognition worker started")
        try:
            while not self._stop_event.is_set():
                try:
                    item = self._audio_queue.get(timeout=0.25)
                except queue.Empty:
                    continue
                if item is _STOP:
                    break
                if not isinstance(item, (bytes, bytearray)):
                    continue
                try:
                    outcome = self._detector.process_audio(bytes(item))
                except Exception:
                    logger.exception("Recognition worker exception")
                    self._schedule_coro(self._on_worker_error("Recognition failed unexpectedly."))
                    break
                if outcome is not None and outcome.activated and outcome.phrase:
                    self._schedule_coro(
                        self._handle_activation(outcome.phrase, outcome.confidence)
                    )
        finally:
            logger.info("Recognition worker exiting")

    def _schedule_coro(self, coro: Any) -> None:
        loop = self._loop
        if loop is None or not loop.is_running():
            logger.warning("No running event loop to bridge wake event")
            try:
                coro.close()
            except Exception:
                pass
            return
        asyncio.run_coroutine_threadsafe(coro, loop)

    async def _on_worker_error(self, message: str) -> None:
        self._last_error = message
        self._status = VoiceServiceStatus.ERROR
        await self._publish_error("RECOGNIZER_ERROR", message)
        await self._publish_status()

    # ------------------------------------------------------------------
    # Activation + state bridge
    # ------------------------------------------------------------------

    async def _handle_activation(self, phrase: str, confidence: float) -> None:
        logger.info(
            "Wake phrase detected phrase=%r confidence=%.3f",
            phrase,
            confidence,
        )
        self._last_activation_at = utc_now()
        self._status = VoiceServiceStatus.ACTIVATION_DETECTED
        self._activation_generation += 1
        generation = self._activation_generation

        if self._event_bus is not None:
            await self._event_bus.publish(
                VOICE_WAKE_DETECTED,
                {"phrase": phrase, "confidence": confidence},
            )
        await self._publish_status()

        if self._state_manager is not None:
            await self._state_manager.set_state(AssistantState.PROCESSING)

        # Cancel any pending return-to-LISTENING from a prior activation
        if self._return_listening_task and not self._return_listening_task.done():
            self._return_listening_task.cancel()

        display_s = self._settings.voice_activation_display_ms / 1000.0
        self._return_listening_task = asyncio.create_task(
            self._return_to_listening(generation, display_s)
        )

    async def _return_to_listening(self, generation: int, delay_s: float) -> None:
        try:
            await asyncio.sleep(delay_s)
        except asyncio.CancelledError:
            return

        if generation != self._activation_generation:
            return
        if self._status not in {
            VoiceServiceStatus.ACTIVATION_DETECTED,
            VoiceServiceStatus.LISTENING,
        }:
            return

        if self._stream is not None and not self._stop_event.is_set():
            self._status = VoiceServiceStatus.LISTENING
            await self._publish_status()
            if self._state_manager is not None:
                await self._state_manager.set_state(AssistantState.LISTENING)

    # ------------------------------------------------------------------
    # Event publishing
    # ------------------------------------------------------------------

    async def _publish_status(self) -> None:
        if self._event_bus is None:
            return
        status = self.get_status()
        await self._event_bus.publish(
            VOICE_STATUS_CHANGED,
            voice_status_to_ws_payload(status),
        )

    async def _publish_error(self, code: str, message: str) -> None:
        if self._event_bus is None:
            return
        await self._event_bus.publish(
            VOICE_ERROR,
            {"code": code, "message": message},
        )


def _resample_linear(samples: np.ndarray, src_rate: int, dst_rate: int) -> np.ndarray:
    """Simple linear resampling — no heavy audio dependency."""
    if src_rate == dst_rate or samples.size == 0:
        return samples
    duration = samples.size / float(src_rate)
    dst_length = max(1, int(round(duration * dst_rate)))
    src_x = np.linspace(0.0, 1.0, num=samples.size, endpoint=False)
    dst_x = np.linspace(0.0, 1.0, num=dst_length, endpoint=False)
    return np.interp(dst_x, src_x, samples).astype(np.float32)
