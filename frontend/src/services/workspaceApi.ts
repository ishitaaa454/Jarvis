import { environment } from '../config/environment';
import type {
  ApplicationActionResult,
  ApplicationRuntimeView,
  WorkspaceStatus,
} from '../types/workspace';

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

export function fetchWorkspaceStatus(): Promise<WorkspaceStatus> {
  return requestJson<WorkspaceStatus>('/api/workspace/status');
}

export async function fetchWorkspaceApplications(): Promise<ApplicationRuntimeView[]> {
  const payload = await requestJson<{ applications: ApplicationRuntimeView[] }>(
    '/api/workspace/applications',
  );
  return payload.applications;
}

export function startWorkspace(): Promise<WorkspaceStatus> {
  return requestJson<WorkspaceStatus>('/api/workspace/start', { method: 'POST' });
}

export function cancelWorkspace(): Promise<WorkspaceStatus> {
  return requestJson<WorkspaceStatus>('/api/workspace/cancel', { method: 'POST' });
}

export function openApplication(appId: string): Promise<ApplicationActionResult> {
  return requestJson<ApplicationActionResult>(
    `/api/workspace/applications/${appId}/open`,
    { method: 'POST' },
  );
}

export function focusApplication(appId: string): Promise<ApplicationActionResult> {
  return requestJson<ApplicationActionResult>(
    `/api/workspace/applications/${appId}/focus`,
    { method: 'POST' },
  );
}

export function refreshWorkspace(): Promise<WorkspaceStatus> {
  return requestJson<WorkspaceStatus>('/api/workspace/refresh', { method: 'POST' });
}
