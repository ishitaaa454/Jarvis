import { useCallback, useEffect, useReducer, useRef, useState, type Dispatch } from 'react';

import {
  fetchMonitorCapabilities,
  fetchMonitorProcesses,
  fetchMonitorSnapshot,
  fetchMonitorStatus,
  refreshMonitor,
  retryMonitorProvider,
} from '../services/systemMonitorApi';
import type { WebSocketMessage } from '../types/messages';
import type {
  CapabilityReport,
  Freshness,
  HistoryPoint,
  ProcessSnapshot,
  SystemMonitorSnapshot,
  SystemMonitorStatus,
} from '../types/systemMonitor';

const HISTORY_CAP = 300;

type SeriesMap = Record<string, HistoryPoint[]>;

type SeriesAction =
  | { type: 'push'; metric: string; point: HistoryPoint }
  | { type: 'replace'; metric: string; points: HistoryPoint[] }
  | { type: 'reset' };

function seriesReducer(state: SeriesMap, action: SeriesAction): SeriesMap {
  switch (action.type) {
    case 'reset':
      return {};
    case 'replace':
      return { ...state, [action.metric]: action.points.slice(-HISTORY_CAP) };
    case 'push': {
      const prev = state[action.metric] ?? [];
      const next = [...prev, action.point].slice(-HISTORY_CAP);
      return { ...state, [action.metric]: next };
    }
    default:
      return state;
  }
}

function pushMetric(
  dispatch: Dispatch<SeriesAction>,
  metric: string,
  value: number | null | undefined,
  timestamp: number,
) {
  dispatch({
    type: 'push',
    metric,
    point: {
      timestamp,
      value: value == null || !Number.isFinite(value) ? null : value,
    },
  });
}

export function computeFreshness(
  collectedAt: string | null | undefined,
  connected: boolean,
  intervalSeconds = 1,
): Freshness {
  if (!connected) return 'STALE';
  if (!collectedAt) return 'UNAVAILABLE';
  const ageMs = Date.now() - new Date(collectedAt).getTime();
  if (!Number.isFinite(ageMs) || ageMs < 0) return 'DELAYED';
  if (ageMs <= intervalSeconds * 2500) return 'LIVE';
  if (ageMs <= intervalSeconds * 8000) return 'DELAYED';
  return 'STALE';
}

export interface UseSystemMonitorResult {
  status: SystemMonitorStatus | null;
  snapshot: SystemMonitorSnapshot | null;
  capabilities: CapabilityReport | null;
  processes: ProcessSnapshot | null;
  series: SeriesMap;
  freshness: Freshness;
  error: string | null;
  loading: boolean;
  refresh: () => Promise<void>;
  refreshProcesses: (opts?: {
    sort?: string;
    order?: string;
    limit?: number;
    search?: string;
  }) => Promise<void>;
  retryProvider: (name: string) => Promise<void>;
  requestRefresh: () => Promise<void>;
  handleSocketMessage: (message: WebSocketMessage) => void;
}

export function useSystemMonitor(connected: boolean): UseSystemMonitorResult {
  const [status, setStatus] = useState<SystemMonitorStatus | null>(null);
  const [snapshot, setSnapshot] = useState<SystemMonitorSnapshot | null>(null);
  const [capabilities, setCapabilities] = useState<CapabilityReport | null>(null);
  const [processes, setProcesses] = useState<ProcessSnapshot | null>(null);
  const [series, dispatchSeries] = useReducer(seriesReducer, {});
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const newestTs = useRef(0);

  const applySnapshot = useCallback((snap: SystemMonitorSnapshot) => {
    const ts = new Date(snap.timestamp).getTime();
    if (Number.isFinite(ts) && ts < newestTs.current) return;
    if (Number.isFinite(ts)) newestTs.current = ts;
    setSnapshot(snap);
    const stamp = ts || Date.now();
    pushMetric(dispatchSeries, 'cpu.usage_percent', snap.cpu.usage_percent, stamp);
    pushMetric(dispatchSeries, 'memory.usage_percent', snap.memory.usage_percent, stamp);
    pushMetric(
      dispatchSeries,
      'disk.read_bytes_per_second',
      snap.disks.activity.read_bytes_per_second,
      stamp,
    );
    pushMetric(
      dispatchSeries,
      'disk.write_bytes_per_second',
      snap.disks.activity.write_bytes_per_second,
      stamp,
    );
    pushMetric(
      dispatchSeries,
      'network.receive_bytes_per_second',
      snap.network.receive_bytes_per_second,
      stamp,
    );
    pushMetric(
      dispatchSeries,
      'network.send_bytes_per_second',
      snap.network.send_bytes_per_second,
      stamp,
    );
    if (snap.battery.present) {
      pushMetric(dispatchSeries, 'battery.percent', snap.battery.percent, stamp);
    }
    if (snap.gpu.devices[0]) {
      pushMetric(dispatchSeries, 'gpu.usage_percent', snap.gpu.devices[0].usage_percent, stamp);
    }
  }, []);

  const refresh = useCallback(async () => {
    try {
      const [statusBody, snapBody, capsBody] = await Promise.all([
        fetchMonitorStatus(),
        fetchMonitorSnapshot(),
        fetchMonitorCapabilities(),
      ]);
      setStatus(statusBody);
      applySnapshot(snapBody);
      if (capsBody && 'cpu' in capsBody) {
        setCapabilities(capsBody as CapabilityReport);
      }
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'System monitor unavailable');
    } finally {
      setLoading(false);
    }
  }, [applySnapshot]);

  const refreshProcesses = useCallback(
    async (opts?: { sort?: string; order?: string; limit?: number; search?: string }) => {
      try {
        const body = await fetchMonitorProcesses(opts);
        setProcesses(body);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Process list unavailable');
      }
    },
    [],
  );

  const retryProvider = useCallback(
    async (name: string) => {
      await retryMonitorProvider(name);
      await refresh();
    },
    [refresh],
  );

  const requestRefresh = useCallback(async () => {
    await refreshMonitor();
    await refresh();
  }, [refresh]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const handleSocketMessage = useCallback(
    (message: WebSocketMessage) => {
      try {
        if (message.type === 'system.monitor_status') {
          setStatus(message.payload as unknown as SystemMonitorStatus);
        } else if (message.type === 'system.metrics') {
          const payload = message.payload as Record<string, unknown>;
          setSnapshot((prev) => {
            const emptyStatic = {
              os_name: null,
              os_release: null,
              os_version: null,
              architecture: null,
              hostname: null,
              python_version: null,
              backend_version: null,
              boot_time: null,
              uptime_seconds: null,
              physical_cores: null,
              logical_cores: null,
              collected_at: null,
            };
            const base: SystemMonitorSnapshot =
              prev ??
              ({
                timestamp: message.timestamp,
                cpu: payload.cpu,
                memory: payload.memory,
                disks: {
                  drives: [],
                  activity: payload.disk_activity,
                  collected_at: null,
                  availability: 'AVAILABLE',
                },
                network: payload.network,
                battery: payload.battery,
                static: emptyStatic,
                gpu: payload.gpu,
                temperatures: payload.temperatures,
                status: 'RUNNING',
                degraded: false,
                capabilities: null,
              } as SystemMonitorSnapshot);
            const next: SystemMonitorSnapshot = {
              ...base,
              timestamp: message.timestamp,
              cpu: (payload.cpu as SystemMonitorSnapshot['cpu']) ?? base.cpu,
              memory: (payload.memory as SystemMonitorSnapshot['memory']) ?? base.memory,
              disks: {
                ...base.disks,
                activity:
                  (payload.disk_activity as SystemMonitorSnapshot['disks']['activity']) ??
                  base.disks.activity,
              },
              network: {
                ...base.network,
                ...((payload.network as object) ?? {}),
                adapters: base.network.adapters,
              },
              battery: (payload.battery as SystemMonitorSnapshot['battery']) ?? base.battery,
              gpu: (payload.gpu as SystemMonitorSnapshot['gpu']) ?? base.gpu,
              temperatures:
                (payload.temperatures as SystemMonitorSnapshot['temperatures']) ??
                base.temperatures,
            };
            applySnapshot(next);
            return next;
          });
        } else if (message.type === 'system.processes_updated') {
          setProcesses(message.payload as unknown as ProcessSnapshot);
        } else if (message.type === 'system.capabilities_changed') {
          setCapabilities(message.payload as unknown as CapabilityReport);
        }
      } catch {
        /* ignore malformed */
      }
    },
    [applySnapshot],
  );

  const freshness = computeFreshness(
    snapshot?.cpu.collected_at ?? snapshot?.timestamp,
    connected,
    1,
  );

  return {
    status,
    snapshot,
    capabilities,
    processes,
    series,
    freshness,
    error,
    loading,
    refresh,
    refreshProcesses,
    retryProvider,
    requestRefresh,
    handleSocketMessage,
  };
}
