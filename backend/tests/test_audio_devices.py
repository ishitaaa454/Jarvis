"""Tests for AudioDeviceManager without real hardware."""

from __future__ import annotations

import pytest

from app.services.voice.audio_devices import AudioDeviceError, AudioDeviceManager


class FakeSoundDevice:
    def __init__(self, devices: list[dict], default_input: int | None = 0) -> None:
        self._devices = devices
        self._default_input = default_input
        self.default = type("D", (), {"device": (default_input, None)})()

    def query_devices(self):
        return self._devices

    def query_hostapis(self):
        return [{"name": "Windows WASAPI"}]


def test_lists_only_input_devices() -> None:
    sd = FakeSoundDevice(
        [
            {
                "name": "Speakers",
                "hostapi": 0,
                "max_input_channels": 0,
                "default_samplerate": 48000,
            },
            {
                "name": "Microphone Array",
                "hostapi": 0,
                "max_input_channels": 2,
                "default_samplerate": 48000,
            },
        ],
        default_input=1,
    )
    manager = AudioDeviceManager(sounddevice_module=sd)
    devices = manager.list_input_devices()
    assert len(devices) == 1
    assert devices[0].name == "Microphone Array"
    assert devices[0].is_default is True
    assert devices[0].host_api == "Windows WASAPI"


def test_get_device_not_found() -> None:
    sd = FakeSoundDevice(
        [
            {
                "name": "Mic",
                "hostapi": 0,
                "max_input_channels": 1,
                "default_samplerate": 16000,
            }
        ],
        default_input=0,
    )
    manager = AudioDeviceManager(sounddevice_module=sd)
    with pytest.raises(AudioDeviceError) as exc:
        manager.get_device(99)
    assert exc.value.code == "DEVICE_NOT_FOUND"


def test_resolve_prefers_configured_id() -> None:
    sd = FakeSoundDevice(
        [
            {
                "name": "Mic A",
                "hostapi": 0,
                "max_input_channels": 1,
                "default_samplerate": 16000,
            },
            {
                "name": "Mic B",
                "hostapi": 0,
                "max_input_channels": 1,
                "default_samplerate": 16000,
            },
        ],
        default_input=0,
    )
    manager = AudioDeviceManager(sounddevice_module=sd)
    device = manager.resolve_device(device_id=1)
    assert device is not None
    assert device.name == "Mic B"


def test_resolve_prefers_physical_mic_when_no_default() -> None:
    sd = FakeSoundDevice(
        [
            {
                "name": "Microsoft Sound Mapper - Input",
                "hostapi": 0,
                "max_input_channels": 2,
                "default_samplerate": 44100,
            },
            {
                "name": "Microphone Array (Intel)",
                "hostapi": 0,
                "max_input_channels": 2,
                "default_samplerate": 48000,
            },
        ],
        default_input=None,
    )
    manager = AudioDeviceManager(sounddevice_module=sd)
    device = manager.resolve_device()
    assert device is not None
    assert "Microphone Array" in device.name


def test_no_devices_returns_empty() -> None:
    sd = FakeSoundDevice([], default_input=None)
    manager = AudioDeviceManager(sounddevice_module=sd)
    assert manager.list_input_devices() == []
    assert manager.get_default_input_device() is None
