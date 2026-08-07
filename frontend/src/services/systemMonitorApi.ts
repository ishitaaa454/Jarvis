import { environment } from '../config/environment';
import type {
  CapabilityReport,
  HistoryPoint,
  ProcessSnapshot,
  SystemMonitorSnapshot,
  SystemMonitorStatus,
} from '../types/systemMonitor';

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

export function fetchMonitorStatus(): Promise<SystemMonitorStatus> {
  return requestJson('/api/system-monitor/status');
}

export function fetchMonitorSnapshot(): Promise<SystemMonitorSnapshot> {
  return requestJson('/api/system-monitor/snapshot');
}

export function fetchMonitorCapabilities(): Promise<CapabilityReport | Record<string, never>> {
  return requestJson('/api/system-monitor/capabilities');
}

export function fetchMonitorHistory(
  metric: string,
  points?: number,
): Promise<{ metric: string; points: HistoryPoint[] }> {
  const query = new URLSearchParams({ metric });
  if (points != null) query.set('points', String(points));
  return requestJson(`/api/system-monitor/history?${query.toString()}`);
}

export function fetchMonitorProcesses(params?: {
  sort?: string;
  order?: string;
  limit?: number;
  search?: string;
}): Promise<ProcessSnapshot> {
  const query = new URLSearchParams();
  if (params?.sort) query.set('sort', params.sort);
  if (params?.order) query.set('order', params.order);
  if (params?.limit != null) query.set('limit', String(params.limit));
  if (params?.search) query.set('search', params.search);
  const suffix = query.toString() ? `?${query}` : '';
  return requestJson(`/api/system-monitor/processes${suffix}`);
}

export function refreshMonitor(): Promise<{ accepted: boolean; status: SystemMonitorStatus }> {
  return requestJson('/api/system-monitor/refresh', { method: 'POST' });
}

export function retryMonitorProvider(
  provider: string,
): Promise<{ accepted: boolean; status: SystemMonitorStatus }> {
  return requestJson(`/api/system-monitor/retry-provider/${provider}`, { method: 'POST' });
}
