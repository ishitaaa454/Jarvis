import { environment } from '../config/environment';
import type { AssistantStateSnapshot, HealthResponse } from '../types/assistant';

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${environment.apiBaseUrl}${path}`, {
    ...init,
    headers: {
      Accept: 'application/json',
      ...(init?.headers ?? {}),
    },
  });

  if (!response.ok) {
    throw new Error(`Request failed (${response.status}) for ${path}`);
  }

  return (await response.json()) as T;
}

export function fetchHealth(): Promise<HealthResponse> {
  return requestJson<HealthResponse>('/api/health');
}

export function fetchState(): Promise<AssistantStateSnapshot> {
  return requestJson<AssistantStateSnapshot>('/api/state');
}
