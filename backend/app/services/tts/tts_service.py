"""Offline Piper TTS service owning synthesis and playback lifecycle."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.core.config import Settings, get_settings
from app.core.events import (
    TTS_ERROR,
    TTS_SEQUENCE_CANCELLED,
    TTS_SEQUENCE_FINISHED,
    TTS_SEQUENCE_STARTED,
    TTS_STATUS_CHANGED,
    TTS_UTTERANCE_FINISHED,
    TTS_UTTERANCE_STARTED,
    EventBus,
)
from app.models.tts import (
    OutputDeviceInfo,
    OutputDeviceStatus,
    TtsServiceStatus,
    TtsStatusResponse,
    tts_status_to_ws_payload,
)
from app.services.tts.audio_output_devices import (
    AudioOutputDeviceManager,
    AudioOutputError,
)
from app.services.tts.audio_player import AudioPlayer, AudioPlayerError
from app.services.tts.piper_engine import PiperEngine, PiperEngineError
from app.services.tts.speech_queue import SpeechQueue, SpeechSequence, SpeechUtterance
from app.utils.time_utils import utc_now

logger = logging.getLogger(__name__)


class SequenceBusyError(Exception):
    """Raised when a welcome sequence is already running."""


class TtsService:
    def __init__(
        self,
        *,
        settings: Settings | None = None,
        event_bus: EventBus | None = None,
        engine: PiperEngine | None = None,
        player: AudioPlayer | None = None,
        device_manager: AudioOutputDeviceManager | None = None,
        speech_queue: SpeechQueue | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._event_bus = event_bus
        self._device_manager = device_manager or AudioOutputDeviceManager()
        self._player = player or AudioPlayer(volume=self._settings.tts_volume)
        self._queue = speech_queue or SpeechQueue(maxsize=self._settings.tts_queue_size)
        self._engine = engine or PiperEngine(
            executable=self._settings.resolved_piper_executable(),
            model_path=self._settings.resolved_piper_model_path(),
            config_path=self._settings.resolved_piper_config_path(),
            length_scale=self._settings.tts_length_scale,
            noise_scale=self._settings.tts_noise_scale,
            noise_width=self._settings.tts_noise_width,
            timeout_seconds=self._settings.tts_synthesis_timeout_seconds,
            temp_dir=self._settings.resolved_tts_temp_dir(),
            delete_temp=self._settings.tts_delete_temp_audio,
        )

        self._status = (
            TtsServiceStatus.DISABLED
            if not self._settings.tts_enabled
            else TtsServiceStatus.STOPPED
        )
        self._lock = asyncio.Lock()
        self._selected_device: OutputDeviceInfo | None = None
        self._model_loaded = False
        self._last_error: str | None = None
        self._last_spoken_at = None
        self._sequence_task: asyncio.Task[None] | None = None
        self._cancel_requested = False
        self._accepting = True
        self._microphone_suppressed = False
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind(self, *, event_bus: EventBus, loop: asyncio.AbstractEventLoop | None = None) -> None:
        self._event_bus = event_bus
        if loop is not None:
            self._loop = loop

    def set_microphone_suppressed(self, value: bool) -> None:
        self._microphone_suppressed = value

    def get_status(self) -> TtsStatusResponse:
        out = None
        if self._selected_device is not None:
            out = OutputDeviceStatus(
                id=self._selected_device.id,
                name=self._selected_device.name,
                is_default=self._selected_device.is_default,
            )
        current = self._queue.current
        return TtsStatusResponse(
            enabled=self._settings.tts_enabled,
            status=self._status,
            engine="Piper",
            voice="en_GB-alan-medium",
            model_loaded=self._model_loaded,
            output_device=out,
            is_speaking=self._status == TtsServiceStatus.SPEAKING,
            current_sequence=self._queue.active_sequence,
            current_utterance_index=current.index if current else None,
            last_spoken_at=self._last_spoken_at,
            last_error=self._last_error,
            volume=self._settings.tts_volume,
            length_scale=self._settings.tts_length_scale,
            sentence_pause_ms=self._settings.welcome_sentence_pause_ms,
            microphone_suppressed=self._microphone_suppressed,
        )

    def list_devices(self) -> list[OutputDeviceInfo]:
        return self._device_manager.list_output_devices()

    def is_sequence_active(self) -> bool:
        return self._queue.is_busy() or (
            self._sequence_task is not None and not self._sequence_task.done()
        )

    async def on_startup(self) -> None:
        self._loop = asyncio.get_running_loop()
        logger.info("TTS service initializing (enabled=%s)", self._settings.tts_enabled)
        if not self._settings.tts_enabled:
            self._status = TtsServiceStatus.DISABLED
            await self._publish_status()
            return
        await self.retry_validation()

    async def retry_validation(self) -> TtsStatusResponse:
        async with self._lock:
            if not self._settings.tts_enabled:
                self._status = TtsServiceStatus.DISABLED
                await self._publish_status()
                return self.get_status()

            self._status = TtsServiceStatus.VALIDATING
            await self._publish_status()
            try:
                self._engine.validate()
                self._model_loaded = True
                self._selected_device = self._device_manager.resolve_device(
                    self._settings.tts_output_device_id,
                    self._settings.tts_output_device_name or None,
                )
                if self._selected_device is None:
                    self._status = TtsServiceStatus.OUTPUT_UNAVAILABLE
                    self._last_error = "No audio output devices are available."
                    await self._publish_error("OUTPUT_UNAVAILABLE", self._last_error)
                else:
                    self._status = TtsServiceStatus.READY
                    self._last_error = None
                    logger.info(
                        "TTS ready voice=en_GB-alan-medium output=%r",
                        self._selected_device.name,
                    )
            except PiperEngineError as exc:
                self._model_loaded = False
                self._last_error = exc.user_message
                if exc.code == "ENGINE_MISSING":
                    self._status = TtsServiceStatus.ENGINE_MISSING
                elif exc.code == "MODEL_MISSING":
                    self._status = TtsServiceStatus.MODEL_MISSING
                else:
                    self._status = TtsServiceStatus.ERROR
                await self._publish_error(exc.code, exc.user_message)
            except AudioOutputError as exc:
                self._status = TtsServiceStatus.OUTPUT_UNAVAILABLE
                self._last_error = exc.user_message
                await self._publish_error(exc.code, exc.user_message)
            except Exception as exc:
                self._status = TtsServiceStatus.ERROR
                self._last_error = f"TTS validation failed: {exc}"
                logger.exception("TTS validation failed")
                await self._publish_error("TTS_VALIDATION_FAILED", self._last_error)

            await self._publish_status()
            return self.get_status()

    async def set_device(self, device_id: int) -> TtsStatusResponse:
        async with self._lock:
            if self.is_sequence_active():
                await self._cancel_locked()
            try:
                device = self._device_manager.get_device(device_id)
            except AudioOutputError as exc:
                self._last_error = exc.user_message
                await self._publish_error(exc.code, exc.user_message)
                raise
            self._selected_device = device
            self._last_error = None
            if self._status not in {
                TtsServiceStatus.DISABLED,
                TtsServiceStatus.ENGINE_MISSING,
                TtsServiceStatus.MODEL_MISSING,
            }:
                self._status = TtsServiceStatus.READY
            await self._publish_status()
            return self.get_status()

    async def speak_welcome_sequence(self) -> None:
        """Speak the fixed three-line welcome sequence. Raises SequenceBusyError if busy."""
        async with self._lock:
            if not self._accepting:
                raise RuntimeError("TTS service is shutting down")
            if self.is_sequence_active():
                raise SequenceBusyError("Welcome sequence is already running")
            if self._status in {
                TtsServiceStatus.DISABLED,
                TtsServiceStatus.ENGINE_MISSING,
                TtsServiceStatus.MODEL_MISSING,
                TtsServiceStatus.OUTPUT_UNAVAILABLE,
            }:
                raise PiperEngineError(
                    self._last_error or f"TTS is not ready ({self._status.value})",
                    code=self._status.value,
                )

            lines = self._settings.welcome_lines()
            if len(lines) != 3:
                raise RuntimeError("Welcome sequence must contain exactly three lines")

            utterances = [
                SpeechUtterance(index=i + 1, total=3, text=line, sequence="welcome")
                for i, line in enumerate(lines)
            ]
            self._queue.begin_sequence(
                SpeechSequence(name="welcome", utterances=utterances)
            )
            self._cancel_requested = False
            self._sequence_task = asyncio.create_task(self._run_sequence())

        await self._sequence_task

    async def cancel(self) -> TtsStatusResponse:
        async with self._lock:
            await self._cancel_locked()
            return self.get_status()

    async def shutdown(self) -> None:
        self._accepting = False
        async with self._lock:
            await self._cancel_locked()
            self._engine.stop()
            self._engine.cleanup_cache()
            if self._status != TtsServiceStatus.DISABLED:
                self._status = TtsServiceStatus.STOPPED
            await self._publish_status()
        logger.info("TTS service shutdown complete")

    async def _cancel_locked(self) -> None:
        self._cancel_requested = True
        self._player.cancel()
        self._engine.stop()
        self._queue.cancel()
        task = self._sequence_task
        self._sequence_task = None
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            except Exception:
                logger.exception("Error while cancelling TTS sequence")
        if self._status not in {
            TtsServiceStatus.DISABLED,
            TtsServiceStatus.ENGINE_MISSING,
            TtsServiceStatus.MODEL_MISSING,
            TtsServiceStatus.OUTPUT_UNAVAILABLE,
            TtsServiceStatus.ERROR,
        }:
            previous = self._status
            self._status = TtsServiceStatus.READY if self._model_loaded else TtsServiceStatus.STOPPED
            if previous in {TtsServiceStatus.SPEAKING, TtsServiceStatus.SYNTHESIZING, TtsServiceStatus.CANCELLING}:
                await self._publish(
                    TTS_SEQUENCE_CANCELLED,
                    {"sequence": "welcome", "completed": False},
                )
        await self._publish_status()

    async def _run_sequence(self) -> None:
        try:
            await self._publish(
                TTS_SEQUENCE_STARTED,
                {"sequence": "welcome", "total_utterances": 3},
            )
            pause_s = self._settings.welcome_sentence_pause_ms / 1000.0
            index = 0
            while True:
                if self._cancel_requested:
                    break
                utterance = self._queue.pop_next()
                if utterance is None:
                    break
                index = utterance.index
                await self._speak_utterance(utterance)
                if self._cancel_requested:
                    break
                if utterance.index < utterance.total and pause_s > 0:
                    await asyncio.sleep(pause_s)

            if self._cancel_requested:
                await self._publish(
                    TTS_SEQUENCE_CANCELLED,
                    {"sequence": "welcome", "completed": False},
                )
            else:
                await self._publish(
                    TTS_SEQUENCE_FINISHED,
                    {"sequence": "welcome", "completed": True},
                )
                self._last_spoken_at = utc_now()
        except Exception as exc:
            message = str(exc)
            logger.exception("Welcome sequence failed")
            self._last_error = message
            self._status = TtsServiceStatus.ERROR
            await self._publish_error("SEQUENCE_FAILED", message)
            await self._publish_status()
            raise
        finally:
            self._queue.mark_idle()
            self._player.reset_cancel()
            if self._status not in {
                TtsServiceStatus.ERROR,
                TtsServiceStatus.DISABLED,
                TtsServiceStatus.ENGINE_MISSING,
                TtsServiceStatus.MODEL_MISSING,
                TtsServiceStatus.OUTPUT_UNAVAILABLE,
            }:
                self._status = TtsServiceStatus.READY if self._model_loaded else TtsServiceStatus.STOPPED
            await self._publish_status()

    async def _speak_utterance(self, utterance: SpeechUtterance) -> None:
        await self._publish(
            TTS_UTTERANCE_STARTED,
            {
                "sequence": utterance.sequence,
                "index": utterance.index,
                "total": utterance.total,
                "text": utterance.text,
            },
        )
        self._status = TtsServiceStatus.SYNTHESIZING
        await self._publish_status()

        audio = await asyncio.to_thread(self._engine.synthesize, utterance.text)
        if self._cancel_requested:
            return

        self._status = TtsServiceStatus.SPEAKING
        await self._publish_status()
        device_id = self._selected_device.id if self._selected_device else None
        try:
            await asyncio.to_thread(self._player.play, audio, device_id=device_id)
        except AudioPlayerError:
            raise
        finally:
            if self._settings.tts_delete_temp_audio and audio.path:
                # Keep cache managed by engine; per-utterance files stay until cache clear
                pass

        await self._publish(
            TTS_UTTERANCE_FINISHED,
            {
                "sequence": utterance.sequence,
                "index": utterance.index,
                "total": utterance.total,
            },
        )
        logger.info(
            "Utterance finished index=%s/%s",
            utterance.index,
            utterance.total,
        )

    async def _publish_status(self) -> None:
        await self._publish(TTS_STATUS_CHANGED, tts_status_to_ws_payload(self.get_status()))

    async def _publish_error(self, code: str, message: str) -> None:
        await self._publish(TTS_ERROR, {"code": code, "message": message})

    async def _publish(self, event_type: str, payload: dict[str, Any]) -> None:
        if self._event_bus is None:
            return
        await self._event_bus.publish(event_type, payload)
