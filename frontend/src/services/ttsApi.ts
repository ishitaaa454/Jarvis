import { environment } from '../config/environment';
import type { OutputDeviceInfo, TtsStatus } from '../types/speech';

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
      if (typeof body.detail === 'string') detail = body.detail;
    } catch {
      // keep default
    }
    throw new Error(detail);
  }
  return (await response.json()) as T;
}

export function fetchTtsStatus(): Promise<TtsStatus> {
  return requestJson<TtsStatus>('/api/tts/status');
}

export async function fetchTtsDevices(): Promise<OutputDeviceInfo[]> {
  const payload = await requestJson<{ devices: OutputDeviceInfo[] }>('/api/tts/devices');
  return payload.devices;
}

export function selectTtsDevice(deviceId: number): Promise<TtsStatus> {
  return requestJson<TtsStatus>('/api/tts/device', {
    method: 'PUT',
    body: JSON.stringify({ device_id: deviceId }),
  });
}

export function testWelcomeSequence(): Promise<TtsStatus> {
  return requestJson<TtsStatus>('/api/tts/test-welcome', { method: 'POST' });
}

export function cancelSpeech(): Promise<TtsStatus> {
  return requestJson<TtsStatus>('/api/tts/cancel', { method: 'POST' });
}

export function retryTts(): Promise<TtsStatus> {
  return requestJson<TtsStatus>('/api/tts/retry', { method: 'POST' });
}
