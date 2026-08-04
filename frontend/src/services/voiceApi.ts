import { environment } from '../config/environment';
import type { AudioDevice, VoiceStatus } from '../types/voice';

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${environment.apiBaseUrl}${path}`, {
    ...init,
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
      ...(init?.headers ?? {}),
    },
  });

  if (!response.ok) {
    let detail = `Request failed (${response.status}) for ${path}`;
    try {
      const body = (await response.json()) as { detail?: unknown };
      if (typeof body.detail === 'string') {
        detail = body.detail;
      }
    } catch {
      // keep default message
    }
    throw new Error(detail);
  }

  return (await response.json()) as T;
}

export function fetchVoiceStatus(): Promise<VoiceStatus> {
  return requestJson<VoiceStatus>('/api/voice/status');
}

export async function fetchVoiceDevices(): Promise<AudioDevice[]> {
  const payload = await requestJson<{ devices: AudioDevice[] }>('/api/voice/devices');
  return payload.devices;
}

export function startVoiceListener(): Promise<VoiceStatus> {
  return requestJson<VoiceStatus>('/api/voice/start', { method: 'POST' });
}

export function stopVoiceListener(): Promise<VoiceStatus> {
  return requestJson<VoiceStatus>('/api/voice/stop', { method: 'POST' });
}

export function selectVoiceDevice(deviceId: number): Promise<VoiceStatus> {
  return requestJson<VoiceStatus>('/api/voice/device', {
    method: 'PUT',
    body: JSON.stringify({ device_id: deviceId }),
  });
}
