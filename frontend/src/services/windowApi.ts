import { environment } from '../config/environment';
import type { RecentWindowRecord, WindowFocusResult, WindowInventorySnapshot } from '../types/windows';

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

export function fetchWindowInventory(): Promise<WindowInventorySnapshot> {
  return requestJson('/api/windows');
}

export function fetchRecentWindows(): Promise<{ recent: RecentWindowRecord[] }> {
  return requestJson('/api/windows/recent');
}

export function refreshWindowInventory(): Promise<{ accepted: boolean }> {
  return requestJson('/api/windows/refresh', { method: 'POST' });
}

export function focusWindow(windowId: string): Promise<WindowFocusResult> {
  return requestJson(`/api/windows/${encodeURIComponent(windowId)}/focus`, { method: 'POST' });
}

export function restoreWindow(windowId: string): Promise<WindowFocusResult> {
  return requestJson(`/api/windows/${encodeURIComponent(windowId)}/restore`, { method: 'POST' });
}

export function previewUrl(windowId: string): string {
  return `${environment.apiBaseUrl}/api/windows/${encodeURIComponent(windowId)}/preview`;
}
