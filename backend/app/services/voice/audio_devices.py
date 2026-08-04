"""Microphone input device discovery via sounddevice."""

from __future__ import annotations

import logging
from typing import Any, Protocol

from app.models.voice import AudioDeviceInfo

logger = logging.getLogger(__name__)


class SoundDeviceModule(Protocol):
    """Minimal protocol so tests can inject a fake sounddevice module."""

    def query_devices(self) -> Any: ...

    def query_hostapis(self) -> Any: ...

    @property
    def default(self) -> Any: ...


class AudioDeviceError(Exception):
    """Raised when microphone discovery or selection fails."""

    def __init__(self, message: str, *, code: str = "DEVICE_ERROR") -> None:
        super().__init__(message)
        self.code = code
        self.user_message = message


class AudioDeviceManager:
    """Lists and validates Windows microphone input devices."""

    def __init__(self, sounddevice_module: SoundDeviceModule | None = None) -> None:
        self._sd = sounddevice_module

    def _load_sounddevice(self) -> SoundDeviceModule:
        if self._sd is not None:
            return self._sd
        try:
            import sounddevice as sd
        except ImportError as exc:
            raise AudioDeviceError(
                "sounddevice is not installed. Install backend requirements.",
                code="SOUNDDEVICE_MISSING",
            ) from exc
        self._sd = sd
        return sd

    def list_input_devices(self) -> list[AudioDeviceInfo]:
        """Return input-capable devices only (exclude output-only)."""
        sd = self._load_sounddevice()
        try:
            devices = sd.query_devices()
            hostapis = sd.query_hostapis()
            default_input = self._default_input_index(sd)
        except AudioDeviceError:
            raise
        except Exception as exc:
            logger.exception("Failed to query audio devices")
            raise AudioDeviceError(
                "Unable to enumerate microphones on this system.",
                code="DEVICE_ENUM_FAILED",
            ) from exc

        results: list[AudioDeviceInfo] = []
        for index, device in enumerate(devices):
            max_in = int(device.get("max_input_channels", 0) or 0)
            if max_in <= 0:
                continue
            host_api_index = int(device.get("hostapi", 0) or 0)
            host_name = "Unknown"
            try:
                host_name = str(hostapis[host_api_index].get("name", "Unknown"))
            except Exception:
                host_name = "Unknown"

            results.append(
                AudioDeviceInfo(
                    id=index,
                    name=str(device.get("name", f"Device {index}")),
                    host_api=host_name,
                    max_input_channels=max_in,
                    default_sample_rate=float(
                        device.get("default_samplerate", 16000) or 16000
                    ),
                    is_default=default_input is not None and index == default_input,
                )
            )
        return results

    def get_default_input_device(self) -> AudioDeviceInfo | None:
        devices = self.list_input_devices()
        for device in devices:
            if device.is_default:
                return device
        return devices[0] if devices else None

    def get_device(self, device_id: int) -> AudioDeviceInfo:
        devices = self.list_input_devices()
        for device in devices:
            if device.id == device_id:
                return device
        raise AudioDeviceError(
            f"Microphone device id {device_id} was not found or has no input channels.",
            code="DEVICE_NOT_FOUND",
        )

    def resolve_device(
        self,
        device_id: int | None = None,
        device_name: str | None = None,
    ) -> AudioDeviceInfo | None:
        """Resolve a configured device; prefer id, then name, then system default."""
        devices = self.list_input_devices()
        if not devices:
            return None

        if device_id is not None:
            for device in devices:
                if device.id == device_id:
                    return device
            raise AudioDeviceError(
                f"Configured microphone id {device_id} is unavailable.",
                code="DEVICE_NOT_FOUND",
            )

        if device_name:
            needle = device_name.strip().lower()
            for device in devices:
                if device.name.strip().lower() == needle:
                    return device
            logger.warning(
                "Configured VOICE_DEVICE_NAME %r not found; falling back to default",
                device_name,
            )

        for device in devices:
            if device.is_default:
                return device
        return self._prefer_physical_microphone(devices) or devices[0]

    @staticmethod
    def _prefer_physical_microphone(
        devices: list[AudioDeviceInfo],
    ) -> AudioDeviceInfo | None:
        """Prefer a real mic over generic mappers when Windows reports no default."""
        ranked: list[tuple[int, AudioDeviceInfo]] = []
        for device in devices:
            name = device.name.lower()
            host = device.host_api.lower()
            score = 0
            if "mapper" in name or "primary sound capture" in name:
                score -= 50
            if "stereo mix" in name or "pc speaker" in name:
                score -= 40
            if "microphone" in name or "mic" in name:
                score += 20
            if "array" in name:
                score += 10
            if "wasapi" in host:
                score += 15
            elif "directsound" in host:
                score += 5
            ranked.append((score, device))
        ranked.sort(key=lambda item: item[0], reverse=True)
        if not ranked or ranked[0][0] <= 0:
            return None
        return ranked[0][1]

    @staticmethod
    def _default_input_index(sd: SoundDeviceModule) -> int | None:
        try:
            default = sd.default.device
            if isinstance(default, (list, tuple)) and default:
                value = default[0]
                return int(value) if value is not None else None
            if isinstance(default, int):
                return default
        except Exception:
            logger.debug("Could not resolve default input device index", exc_info=True)
        return None
