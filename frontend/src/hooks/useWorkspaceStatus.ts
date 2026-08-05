import { useCallback, useEffect, useRef, useState } from 'react';

import {
  cancelWorkspace,
  fetchWorkspaceApplications,
  fetchWorkspaceStatus,
  focusApplication,
  openApplication,
  refreshWorkspace,
  startWorkspace,
} from '../services/workspaceApi';
import type { WebSocketMessage } from '../types/messages';
import type {
  ApplicationActionResult,
  ApplicationActionStatus,
  ApplicationRuntimeStatus,
  ApplicationRuntimeView,
  WorkspaceApplicationResultPayload,
  WorkspaceApplicationStatusPayload,
  WorkspaceErrorPayload,
  WorkspaceRunFinishedPayload,
  WorkspaceStatus,
  WorkspaceStatusChangedPayload,
  WorkspaceWarningPayload,
} from '../types/workspace';

const BANNER_HOLD_MS = 4000;

export type WorkspaceBanner = 'OPENING' | 'READY' | 'PARTIAL' | null;

export interface UseWorkspaceStatusResult {
  workspaceStatus: WorkspaceStatus | null;
  applications: ApplicationRuntimeStatus[];
  loading: boolean;
  error: string | null;
  pending: boolean;
  pendingAppIds: Set<string>;
  banner: WorkspaceBanner;
  isRunning: boolean;
  refresh: () => Promise<void>;
  start: () => Promise<void>;
  cancel: () => Promise<void>;
  reloadRegistry: () => Promise<void>;
  openApp: (appId: string) => Promise<void>;
  focusApp: (appId: string) => Promise<void>;
  handleSocketMessage: (message: WebSocketMessage) => void;
}

function viewToRuntime(
  view: ApplicationRuntimeView,
  previousStatus?: ApplicationActionStatus,
): ApplicationRuntimeStatus {
  return {
    applicationId: view.id,
    displayName: view.display_name,
    status: previousStatus ?? view.status,
    running: view.running,
    windowFound: view.window_found,
    focusSucceeded: false,
    processId: null,
    error: null,
    result: view.last_result,
    durationMs: null,
    enabled: view.enabled,
    order: view.order,
    launchType: view.launch_type,
    resolved: view.resolved,
  };
}

function resultToRuntime(
  previous: ApplicationRuntimeStatus | undefined,
  result: ApplicationActionResult,
): ApplicationRuntimeStatus {
  return {
    applicationId: result.application_id,
    displayName: result.display_name,
    status: result.status,
    running: result.running,
    windowFound: result.window_found,
    focusSucceeded: result.focus_succeeded,
    processId: result.process_id,
    error: result.error,
    result: result.result,
    durationMs: result.duration_ms,
    enabled: previous?.enabled ?? true,
    order: previous?.order ?? 100,
    launchType: previous?.launchType ?? 'executable',
    resolved: previous?.resolved ?? true,
  };
}

export function useWorkspaceStatus(): UseWorkspaceStatusResult {
  const [workspaceStatus, setWorkspaceStatus] = useState<WorkspaceStatus | null>(null);
  const [appMap, setAppMap] = useState<Map<string, ApplicationRuntimeStatus>>(new Map());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [pendingAppIds, setPendingAppIds] = useState<Set<string>>(new Set());
  const [banner, setBanner] = useState<WorkspaceBanner>(null);
  const bannerTimer = useRef<number | null>(null);

  const clearBannerTimer = useCallback(() => {
    if (bannerTimer.current !== null) {
      window.clearTimeout(bannerTimer.current);
      bannerTimer.current = null;
    }
  }, []);

  const showTimedBanner = useCallback(
    (next: WorkspaceBanner) => {
      setBanner(next);
      clearBannerTimer();
      if (next === 'READY' || next === 'PARTIAL') {
        bannerTimer.current = window.setTimeout(() => {
          setBanner(null);
          bannerTimer.current = null;
        }, BANNER_HOLD_MS);
      }
    },
    [clearBannerTimer],
  );

  const loadApplications = useCallback(async () => {
    try {
      const views = await fetchWorkspaceApplications();
      setAppMap((prev) => {
        const next = new Map<string, ApplicationRuntimeStatus>();
        for (const view of views) {
          next.set(view.id, viewToRuntime(view, prev.get(view.id)?.status));
        }
        return next;
      });
    } catch {
      // Application list failures are non-fatal; workspace status errors take priority.
    }
  }, []);

  const refresh = useCallback(async () => {
    try {
      const status = await fetchWorkspaceStatus();
      setWorkspaceStatus(status);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to load workspace status');
    } finally {
      setLoading(false);
    }
    await loadApplications();
  }, [loadApplications]);

  useEffect(() => {
    void refresh();
    return () => clearBannerTimer();
    // Intentionally run once on mount; `refresh` is stable enough for our purposes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const start = useCallback(async () => {
    setPending(true);
    setError(null);
    try {
      const status = await startWorkspace();
      setWorkspaceStatus(status);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start workspace');
      await refresh();
    } finally {
      setPending(false);
    }
  }, [refresh]);

  const cancel = useCallback(async () => {
    setPending(true);
    setError(null);
    try {
      const status = await cancelWorkspace();
      setWorkspaceStatus(status);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to cancel workspace');
    } finally {
      setPending(false);
      await refresh();
    }
  }, [refresh]);

  const reloadRegistry = useCallback(async () => {
    setPending(true);
    setError(null);
    try {
      const status = await refreshWorkspace();
      setWorkspaceStatus(status);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to refresh workspace registry');
    } finally {
      setPending(false);
      await loadApplications();
    }
  }, [loadApplications]);

  const setAppPending = useCallback((appId: string, isPending: boolean) => {
    setPendingAppIds((prev) => {
      const next = new Set(prev);
      if (isPending) {
        next.add(appId);
      } else {
        next.delete(appId);
      }
      return next;
    });
  }, []);

  const openApp = useCallback(
    async (appId: string) => {
      setAppPending(appId, true);
      setError(null);
      try {
        const result = await openApplication(appId);
        setAppMap((prev) => {
          const next = new Map(prev);
          next.set(appId, resultToRuntime(next.get(appId), result));
          return next;
        });
      } catch (err) {
        setError(err instanceof Error ? err.message : `Failed to open application ${appId}`);
      } finally {
        setAppPending(appId, false);
      }
    },
    [setAppPending],
  );

  const focusApp = useCallback(
    async (appId: string) => {
      setAppPending(appId, true);
      setError(null);
      try {
        const result = await focusApplication(appId);
        setAppMap((prev) => {
          const next = new Map(prev);
          next.set(appId, resultToRuntime(next.get(appId), result));
          return next;
        });
      } catch (err) {
        setError(err instanceof Error ? err.message : `Failed to focus application ${appId}`);
      } finally {
        setAppPending(appId, false);
      }
    },
    [setAppPending],
  );

  const handleSocketMessage = useCallback(
    (message: WebSocketMessage) => {
      switch (message.type) {
        case 'workspace.status_changed': {
          const payload = message.payload as unknown as WorkspaceStatusChangedPayload;
          setWorkspaceStatus((prev) => {
            const base: WorkspaceStatus = prev ?? {
              enabled: true,
              status: payload.status,
              active_run_id: payload.active_run_id,
              profile: payload.profile,
              total_configured: 0,
              total_enabled: payload.total_enabled,
              current_application: payload.current_application,
              progress: payload.progress,
              last_run: null,
              last_error: payload.last_error,
            };
            return {
              ...base,
              status: payload.status,
              active_run_id: payload.active_run_id,
              profile: payload.profile,
              total_enabled: payload.total_enabled,
              current_application: payload.current_application,
              progress: payload.progress,
              last_error: payload.last_error,
            };
          });
          setLoading(false);
          if (payload.status === 'PREPARING' || payload.status === 'LAUNCHING') {
            setBanner('OPENING');
          }
          return;
        }

        case 'workspace.run_started': {
          showTimedBanner('OPENING');
          setAppMap((prev) => {
            const next = new Map<string, ApplicationRuntimeStatus>();
            for (const [id, status] of prev) {
              next.set(id, { ...status, status: 'PENDING', error: null, result: null });
            }
            return next;
          });
          return;
        }

        case 'workspace.application_status': {
          const payload = message.payload as unknown as WorkspaceApplicationStatusPayload;
          setAppMap((prev) => {
            const next = new Map(prev);
            const existing = next.get(payload.application_id);
            next.set(payload.application_id, {
              applicationId: payload.application_id,
              displayName: payload.display_name,
              status: payload.status,
              running: existing?.running ?? false,
              windowFound: existing?.windowFound ?? false,
              focusSucceeded: existing?.focusSucceeded ?? false,
              processId: existing?.processId ?? null,
              error: existing?.error ?? null,
              result: existing?.result ?? null,
              durationMs: existing?.durationMs ?? null,
              enabled: existing?.enabled ?? true,
              order: existing?.order ?? 100,
              launchType: existing?.launchType ?? 'executable',
              resolved: existing?.resolved ?? true,
            });
            return next;
          });
          return;
        }

        case 'workspace.application_result': {
          const payload = message.payload as unknown as WorkspaceApplicationResultPayload;
          setAppMap((prev) => {
            const next = new Map(prev);
            next.set(
              payload.application_id,
              resultToRuntime(next.get(payload.application_id), payload),
            );
            return next;
          });
          return;
        }

        case 'workspace.run_finished': {
          const payload = message.payload as unknown as WorkspaceRunFinishedPayload;
          if (payload.status === 'READY') {
            showTimedBanner('READY');
          } else if (payload.status === 'PARTIAL_SUCCESS') {
            showTimedBanner('PARTIAL');
          } else {
            setBanner(null);
            clearBannerTimer();
          }
          void refresh();
          return;
        }

        case 'workspace.run_cancelled': {
          setBanner(null);
          clearBannerTimer();
          void refresh();
          return;
        }

        case 'workspace.warning': {
          const payload = message.payload as unknown as WorkspaceWarningPayload;
          setError(payload.message);
          return;
        }

        case 'workspace.error': {
          const payload = message.payload as unknown as WorkspaceErrorPayload;
          setBanner(null);
          clearBannerTimer();
          setError(payload.message);
          return;
        }

        default:
          return;
      }
    },
    [clearBannerTimer, refresh, showTimedBanner],
  );

  const isRunning =
    workspaceStatus?.status === 'PREPARING' ||
    workspaceStatus?.status === 'LAUNCHING' ||
    workspaceStatus?.status === 'CANCELLING';

  const applications = Array.from(appMap.values()).sort((a, b) => a.order - b.order);

  return {
    workspaceStatus,
    applications,
    loading,
    error,
    pending,
    pendingAppIds,
    banner,
    isRunning,
    refresh,
    start,
    cancel,
    reloadRegistry,
    openApp,
    focusApp,
    handleSocketMessage,
  };
}

export function describeWorkspaceStatus(
  status: WorkspaceStatus['status'] | undefined,
): string {
  switch (status) {
    case 'IDLE':
      return 'Idle';
    case 'PREPARING':
      return 'Preparing';
    case 'LAUNCHING':
      return 'Launching';
    case 'CANCELLING':
      return 'Cancelling';
    case 'READY':
      return 'Ready';
    case 'PARTIAL_SUCCESS':
      return 'Partially ready';
    case 'CANCELLED':
      return 'Cancelled';
    case 'ERROR':
      return 'Error';
    default:
      return 'Unknown';
  }
}

export function describeApplicationStatus(
  status: ApplicationActionStatus | undefined,
): string {
  switch (status) {
    case 'PENDING':
      return 'Pending';
    case 'CHECKING':
      return 'Checking';
    case 'ALREADY_RUNNING':
      return 'Already running';
    case 'RESTORING':
      return 'Restoring';
    case 'FOCUSING':
      return 'Focusing';
    case 'LAUNCHING':
      return 'Launching';
    case 'OPENING_URL':
      return 'Opening URL';
    case 'OPENING_URI':
      return 'Opening URI';
    case 'WAITING_FOR_STARTUP':
      return 'Waiting for startup';
    case 'READY':
      return 'Ready';
    case 'SKIPPED':
      return 'Skipped';
    case 'FAILED':
      return 'Failed';
    case 'CANCELLED':
      return 'Cancelled';
    default:
      return 'Unknown';
  }
}
