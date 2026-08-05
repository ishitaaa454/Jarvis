"""Coordinates wake detection with TTS welcome sequence and mic suppression."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from app.core.config import Settings, get_settings
from app.core.events import (
    ASSISTANT_ACTIVATION_FINISHED,
    ASSISTANT_ACTIVATION_STARTED,
    ASSISTANT_WORKSPACE_INITIALIZATION_STARTED,
    ASSISTANT_WORKSPACE_READY,
    VOICE_WAKE_DETECTED,
    WORKSPACE_ERROR,
    EventBus,
)
from app.core.state_manager import StateManager
from app.models.application import WorkspaceServiceStatus
from app.models.assistant_state import AssistantState
from app.services.tts.piper_engine import PiperEngineError
from app.services.tts.tts_service import SequenceBusyError, TtsService

if TYPE_CHECKING:
    from app.services.voice.voice_service import VoiceService
    from app.services.workspace.workspace_service import WorkspaceService

logger = logging.getLogger(__name__)


class ActivationCoordinator:
    """Authoritative owner of the wake → speech → resume-listening flow.

    Phase 2's delayed return-to-LISTENING is disabled when this coordinator is
    bound; overlapping activations are rejected while a sequence is active.
    """

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        state_manager: StateManager | None = None,
        event_bus: EventBus | None = None,
        voice_service: VoiceService | None = None,
        tts_service: TtsService | None = None,
        workspace_service: WorkspaceService | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._state_manager = state_manager
        self._event_bus = event_bus
        self._voice = voice_service
        self._tts = tts_service
        self._workspace = workspace_service
        self._lock = asyncio.Lock()
        self._active = False
        self._task: asyncio.Task[None] | None = None
        self._subscribed = False
        self._wake_was_listening = True

    def bind(
        self,
        *,
        state_manager: StateManager,
        event_bus: EventBus,
        voice_service: VoiceService,
        tts_service: TtsService,
        workspace_service: WorkspaceService | None = None,
    ) -> None:
        self._state_manager = state_manager
        self._event_bus = event_bus
        self._voice = voice_service
        self._tts = tts_service
        if workspace_service is not None:
            self._workspace = workspace_service
        # Disable Phase 2 auto-return; coordinator owns post-wake transitions.
        voice_service.set_activation_handoff(True)

    async def start(self) -> None:
        if self._event_bus is None or self._subscribed:
            return
        await self._event_bus.subscribe(VOICE_WAKE_DETECTED, self._on_wake_event)
        self._subscribed = True
        logger.info("ActivationCoordinator subscribed to wake events")

    async def stop(self) -> None:
        if self._event_bus is not None and self._subscribed:
            await self._event_bus.unsubscribe(VOICE_WAKE_DETECTED, self._on_wake_event)
            self._subscribed = False
        await self.cancel()

    @property
    def is_active(self) -> bool:
        return self._active

    async def _on_wake_event(self, payload: dict) -> None:
        # Do not await the full sequence here — EventBus publish must return promptly.
        asyncio.create_task(
            self._safe_handle_wake(
                phrase=str(payload.get("phrase") or ""),
                confidence=float(payload.get("confidence") or 0.0),
            )
        )

    async def _safe_handle_wake(self, *, phrase: str, confidence: float) -> None:
        try:
            await self.handle_wake(phrase=phrase, confidence=confidence)
        except SequenceBusyError:
            logger.info("Duplicate wake activation rejected (sequence already active)")
        except Exception:
            logger.exception("ActivationCoordinator failed to handle wake event")

    async def handle_wake(
        self,
        *,
        phrase: str = "",
        confidence: float = 0.0,
        from_test: bool = False,
    ) -> None:
        async with self._lock:
            if self._active:
                raise SequenceBusyError("Activation sequence already running")
            self._active = True
            self._task = asyncio.create_task(
                self._run_activation(phrase=phrase, confidence=confidence, from_test=from_test)
            )
        await self._task

    async def run_test_welcome(self) -> None:
        """Development helper: same path as wake, without requiring a phrase."""
        await self.handle_wake(phrase="wake up jarvis", confidence=1.0, from_test=True)

    async def cancel(self) -> None:
        task = self._task
        if self._tts is not None:
            await self._tts.cancel()
        if self._workspace is not None:
            try:
                await self._workspace.cancel()
            except Exception:
                logger.exception("Error cancelling workspace during activation cancel")
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            except Exception:
                logger.exception("Error cancelling activation")
        async with self._lock:
            self._active = False
            self._task = None
        await self._safe_resume_listening(return_idle=False)

    async def _run_activation(
        self,
        *,
        phrase: str,
        confidence: float,
        from_test: bool,
    ) -> None:
        assert self._state_manager is not None
        assert self._voice is not None
        assert self._tts is not None

        try:
            logger.info(
                "Activation started phrase=%r confidence=%.3f test=%s",
                phrase,
                confidence,
                from_test,
            )
            await self._publish(
                ASSISTANT_ACTIVATION_STARTED,
                {"phrase": phrase, "confidence": confidence, "from_test": from_test},
            )

            await self._state_manager.set_state(AssistantState.PROCESSING)

            self._wake_was_listening = self._voice.is_capture_active()
            await self._voice.pause_listening()
            self._tts.set_microphone_suppressed(True)
            logger.info("Microphone paused for speech")

            pre = self._settings.tts_pre_speech_delay_ms / 1000.0
            if pre > 0:
                await asyncio.sleep(pre)

            await self._state_manager.set_state(AssistantState.SPEAKING)
            await self._tts.speak_welcome_sequence()

            post = self._settings.tts_post_speech_delay_ms / 1000.0
            if post > 0:
                await asyncio.sleep(post)

            if self._should_launch_workspace():
                await self._run_workspace_sequence()

            await self._safe_resume_listening(return_idle=from_test and not self._wake_was_listening)
            await self._publish(
                ASSISTANT_ACTIVATION_FINISHED,
                {"completed": True},
            )
            logger.info("Activation finished successfully")
        except asyncio.CancelledError:
            logger.info("Activation cancelled")
            await self._safe_resume_listening(return_idle=from_test and not self._wake_was_listening)
            await self._publish(
                ASSISTANT_ACTIVATION_FINISHED,
                {"completed": False, "cancelled": True},
            )
            raise
        except SequenceBusyError:
            raise
        except (PiperEngineError, Exception) as exc:
            logger.exception("Activation failed: %s", exc)
            await self._safe_resume_listening(return_idle=from_test and not self._wake_was_listening)
            await self._publish(
                ASSISTANT_ACTIVATION_FINISHED,
                {"completed": False, "error": str(exc)},
            )
        finally:
            async with self._lock:
                self._active = False
                self._task = None

    def _should_launch_workspace(self) -> bool:
        return (
            self._workspace is not None
            and self._settings.workspace_enabled
            and self._settings.workspace_start_after_welcome
        )

    async def _run_workspace_sequence(self) -> None:
        """Launch the default workspace after the welcome speech finishes.

        The microphone stays paused for the entire duration of this method —
        callers only resume listening after it returns. Failures (including a
        conflicting run already in progress) are published as warnings/errors
        but never prevent the microphone from resuming afterwards.
        """
        assert self._state_manager is not None
        assert self._workspace is not None
        try:
            logger.info("Starting workspace launch after welcome sequence")
            await self._publish(ASSISTANT_WORKSPACE_INITIALIZATION_STARTED, {})
            await self._state_manager.set_state(AssistantState.INITIALIZING_WORKSPACE)
            await self._state_manager.set_state(AssistantState.OPENING_APPLICATIONS)

            status = await self._workspace.start_default_workspace()

            if status.status in {
                WorkspaceServiceStatus.READY,
                WorkspaceServiceStatus.PARTIAL_SUCCESS,
            }:
                await self._state_manager.set_state(AssistantState.READY)
                await self._publish(ASSISTANT_WORKSPACE_READY, {"status": status.status.value})
                display_s = self._settings.workspace_ready_display_ms / 1000.0
                if display_s > 0:
                    await asyncio.sleep(display_s)
            else:
                message = status.last_error or f"Workspace finished with status {status.status.value}"
                logger.warning("Workspace launch did not complete successfully: %s", message)
                await self._publish(WORKSPACE_ERROR, {"message": message})
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("Workspace launch failed during activation")
            await self._publish(WORKSPACE_ERROR, {"message": str(exc)})

    async def _safe_resume_listening(self, *, return_idle: bool) -> None:
        if self._tts is not None:
            self._tts.set_microphone_suppressed(False)
        if self._voice is not None:
            try:
                await self._voice.resume_listening()
                logger.info("Wake listener resumed")
            except Exception:
                logger.exception("Failed to resume wake listener after speech")
                if self._state_manager is not None:
                    await self._state_manager.set_state(AssistantState.ERROR)
                return

        if self._state_manager is None:
            return
        if return_idle:
            await self._state_manager.set_state(AssistantState.IDLE)
        else:
            await self._state_manager.set_state(AssistantState.LISTENING)

    async def _publish(self, event_type: str, payload: dict) -> None:
        if self._event_bus is None:
            return
        await self._event_bus.publish(event_type, payload)
