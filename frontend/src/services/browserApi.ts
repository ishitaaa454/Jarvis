import { environment } from '../config/environment';
import type { BrowserDestination, BrowserStatus } from '../types/browser';

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

export function fetchBrowserStatus(): Promise<BrowserStatus> {
  return requestJson('/api/browser/status');
}

export function fetchBrowserDestinations(): Promise<{ destinations: BrowserDestination[] }> {
  return requestJson('/api/browser/destinations');
}

export function openBrowserDestination(id: string): Promise<unknown> {
  return requestJson(`/api/browser/destinations/${encodeURIComponent(id)}/open`, {
    method: 'POST',
  });
}

export function focusBrowserDestination(id: string): Promise<unknown> {
  return requestJson(`/api/browser/destinations/${encodeURIComponent(id)}/focus`, {
    method: 'POST',
  });
}
