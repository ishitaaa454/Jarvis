"""Windows audio output device discovery via sounddevice."""

from __future__ import annotations

import logging
from typing import Any, Protocol

from app.models.tts import OutputDeviceInfo

logger = logging.getLogger(__name__)


class SoundDeviceModule(Protocol):
    def query_devices(self) -> Any: ...

    def query_hostapis(self) -> Any: ...

    @property
    def default(self) -> Any: ...


class AudioOutputError(Exception):
    def __init__(self, message: str, *, code: str = "OUTPUT_ERROR") -> None:
        super().__init__(message)
        self.code = code
        self.user_message = message


class AudioOutputDeviceManager:
    def __init__(self, sounddevice_module: SoundDeviceModule | None = None) -> None:
        self._sd = sounddevice_module

    def _load(self) -> SoundDeviceModule:
        if self._sd is not None:
            return self._sd
        try:
            import sounddevice as sd
        except ImportError as exc:
            raise AudioOutputError(
                "sounddevice is not installed.",
                code="SOUNDDEVICE_MISSING",
            ) from exc
        self._sd = sd
        return sd

    def list_output_devices(self) -> list[OutputDeviceInfo]:
        sd = self._load()
        try:
            devices = sd.query_devices()
            hostapis = sd.query_hostapis()
            default_output = self._default_output_index(sd)
        except Exception as exc:
            logger.exception("Failed to query output devices")
            raise AudioOutputError(
                "Unable to enumerate audio output devices.",
                code="OUTPUT_ENUM_FAILED",
            ) from exc

        results: list[OutputDeviceInfo] = []
        for index, device in enumerate(devices):
            max_out = int(device.get("max_output_channels", 0) or 0)
            if max_out <= 0:
                continue
            host_api_index = int(device.get("hostapi", 0) or 0)
            host_name = "Unknown"
            try:
                host_name = str(hostapis[host_api_index].get("name", "Unknown"))
            except Exception:
                host_name = "Unknown"
            results.append(
                OutputDeviceInfo(
                    id=index,
                    name=str(device.get("name", f"Device {index}")),
                    host_api=host_name,
                    max_output_channels=max_out,
                    default_sample_rate=float(
                        device.get("default_samplerate", 48000) or 48000
                    ),
                    is_default=default_output is not None and index == default_output,
                )
            )
        return results

    def get_device(self, device_id: int) -> OutputDeviceInfo:
        for device in self.list_output_devices():
            if device.id == device_id:
                return device
        raise AudioOutputError(
            f"Output device id {device_id} was not found.",
            code="OUTPUT_NOT_FOUND",
        )

    def resolve_device(
        self,
        device_id: int | None = None,
        device_name: str | None = None,
    ) -> OutputDeviceInfo | None:
        devices = self.list_output_devices()
        if not devices:
            return None
        if device_id is not None:
            for device in devices:
                if device.id == device_id:
                    return device
            raise AudioOutputError(
                f"Configured output device id {device_id} is unavailable.",
                code="OUTPUT_NOT_FOUND",
            )
        if device_name:
            needle = device_name.strip().lower()
            for device in devices:
                if device.name.strip().lower() == needle:
                    return device
        for device in devices:
            if device.is_default:
                return device
        return self._prefer_speakers(devices) or devices[0]

    @staticmethod
    def _prefer_speakers(devices: list[OutputDeviceInfo]) -> OutputDeviceInfo | None:
        ranked: list[tuple[int, OutputDeviceInfo]] = []
        for device in devices:
            name = device.name.lower()
            host = device.host_api.lower()
            score = 0
            if "mapper" in name or "primary sound driver" in name:
                score -= 40
            if "speaker" in name or "headphones" in name:
                score += 25
            if "wasapi" in host:
                score += 10
            ranked.append((score, device))
        ranked.sort(key=lambda item: item[0], reverse=True)
        return ranked[0][1] if ranked and ranked[0][0] > 0 else None

    @staticmethod
    def _default_output_index(sd: SoundDeviceModule) -> int | None:
        try:
            default = sd.default.device
            if isinstance(default, (list, tuple)) and len(default) > 1:
                value = default[1]
                return int(value) if value is not None else None
            if isinstance(default, int):
                return default
        except Exception:
            logger.debug("Could not resolve default output device", exc_info=True)
        return None
