import { environment } from '../config/environment';
import type { HotkeyStatus } from '../types/hotkey';

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
    throw new Error(`Request failed (${response.status}) for ${path}`);
  }
  return (await response.json()) as T;
}

export function fetchHotkeyStatus(): Promise<HotkeyStatus> {
  return requestJson('/api/hotkeys/status');
}

export function retryHotkeys(): Promise<HotkeyStatus> {
  return requestJson('/api/hotkeys/retry', { method: 'POST' });
}
