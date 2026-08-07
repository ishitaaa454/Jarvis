import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useReducer,
  useRef,
  useState,
  type ReactNode,
} from 'react';

import { activityReducer } from '../reducers/activityReducer';
import { useHealthMetrics } from '../hooks/useHealthMetrics';
import { useJarvisSocket } from '../hooks/useJarvisSocket';
import { useReducedMotion } from '../hooks/useReducedMotion';
import { useSpeechStatus, type UseSpeechStatusResult } from '../hooks/useSpeechStatus';
import {
  useSystemMonitor,
  type UseSystemMonitorResult,
} from '../hooks/useSystemMonitor';
import { useVoiceStatus, type UseVoiceStatusResult } from '../hooks/useVoiceStatus';
import {
  useWorkspaceStatus,
  type UseWorkspaceStatusResult,
} from '../hooks/useWorkspaceStatus';
import { fetchState } from '../services/api';
import { dispatchDashboardEvent } from '../services/dashboardEventDispatcher';
import type { AssistantState, ConnectionStatus, HealthResponse } from '../types/assistant';
import type {
  DashboardAnnouncement,
  MetricHistoryState,
  TimelineEntry,
} from '../types/dashboard';
import type { ActivityEntry, WebSocketMessage } from '../types/messages';

export interface DashboardContextValue {
  connectionStatus: ConnectionStatus;
  assistantState: AssistantState | null;
  dataStale: boolean;
  connectedAt: string | null;
  health: HealthResponse | null;
  healthError: string | null;
  metricHistory: MetricHistoryState;
  refreshHealth: () => Promise<void>;
  timeline: TimelineEntry[];
  clearTimeline: () => void;
  /** Legacy ActivityLog compatibility */
  activity: ActivityEntry[];
  announcement: DashboardAnnouncement | null;
  tabVisible: boolean;
  reducedMotion: boolean;
  reducedMotionOverride: boolean | null;
  setReducedMotionOverride: (value: boolean | null) => void;
  voice: UseVoiceStatusResult;
  speech: UseSpeechStatusResult;
  workspace: UseWorkspaceStatusResult;
  systemMonitor: UseSystemMonitorResult;
}

const DashboardContext = createContext<DashboardContextValue | null>(null);

export { DashboardContext };

export function DashboardProvider({ children }: { children: ReactNode }) {
  const socket = useJarvisSocket();
  const voice = useVoiceStatus();
  const speech = useSpeechStatus();
  const workspace = useWorkspaceStatus();
  const healthMetrics = useHealthMetrics();
  const systemMonitor = useSystemMonitor(socket.connectionStatus === 'CONNECTED');

  const [assistantState, setAssistantState] = useState<AssistantState | null>(
    socket.assistantState,
  );
  const [timeline, dispatchTimeline] = useReducer(activityReducer, []);
  const [dataStale, setDataStale] = useState(false);
  const [connectedAt, setConnectedAt] = useState<string | null>(null);
  const [announcement, setAnnouncement] = useState<DashboardAnnouncement | null>(null);
  const [tabVisible, setTabVisible] = useState(
    () => typeof document === 'undefined' || document.visibilityState === 'visible',
  );
  const [reducedMotionOverride, setReducedMotionOverride] = useState<boolean | null>(null);
  const reducedMotion = useReducedMotion(reducedMotionOverride);
  const announceTimer = useRef<number | null>(null);
  const previousConnection = useRef<ConnectionStatus | null>(null);

  const clearTimeline = useCallback(() => {
    dispatchTimeline({ type: 'clear' });
  }, []);

  const publishAnnouncement = useCallback(
    (message: string, politeness: 'polite' | 'assertive') => {
      const id = `${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
      setAnnouncement({ id, message, politeness });
      if (announceTimer.current) window.clearTimeout(announceTimer.current);
      announceTimer.current = window.setTimeout(() => setAnnouncement(null), 3500);
    },
    [],
  );

  useEffect(() => {
    const onVisibility = () => {
      setTabVisible(document.visibilityState === 'visible');
    };
    document.addEventListener('visibilitychange', onVisibility);
    return () => document.removeEventListener('visibilitychange', onVisibility);
  }, []);

  useEffect(() => {
    if (socket.assistantState) {
      setAssistantState(socket.assistantState);
    }
  }, [socket.assistantState]);

  useEffect(() => {
    const previous = previousConnection.current;
    if (
      socket.connectionStatus === 'DISCONNECTED' ||
      socket.connectionStatus === 'RECONNECTING' ||
      socket.connectionStatus === 'ERROR'
    ) {
      setDataStale(true);
      if (
        previous === 'CONNECTED' &&
        (socket.connectionStatus === 'DISCONNECTED' ||
          socket.connectionStatus === 'RECONNECTING')
      ) {
        publishAnnouncement('Connection lost', 'assertive');
      }
    }
  }, [socket.connectionStatus, publishAnnouncement]);

  useEffect(() => {
    const handler = (message: WebSocketMessage) => {
      try {
        const effects = dispatchDashboardEvent(message);
        if (effects.assistantState) {
          setAssistantState(effects.assistantState);
        }
        if (effects.timeline) {
          dispatchTimeline({ type: 'append', entry: effects.timeline });
        }
        if (effects.announcement) {
          publishAnnouncement(
            effects.announcement.message,
            effects.announcement.politeness,
          );
        }
        if (effects.markLive) {
          setDataStale(false);
        }
      } catch (err) {
        if (import.meta.env.DEV) {
          console.warn('[dashboard] Event dispatch failed', err);
        }
      }
      voice.handleSocketMessage(message);
      speech.handleSocketMessage(message);
      workspace.handleSocketMessage(message);
      systemMonitor.handleSocketMessage(message);
    };
    socket.registerMessageHandler(handler);
    return () => socket.registerMessageHandler(null);
  }, [
    socket.registerMessageHandler,
    voice.handleSocketMessage,
    speech.handleSocketMessage,
    workspace.handleSocketMessage,
    systemMonitor.handleSocketMessage,
    publishAnnouncement,
  ]);

  useEffect(() => {
    const previous = previousConnection.current;
    previousConnection.current = socket.connectionStatus;
    if (socket.connectionStatus !== 'CONNECTED') return;
    setConnectedAt((prev) => prev ?? new Date().toISOString());
    setDataStale(false);
    void voice.refresh();
    void speech.refresh();
    void workspace.refresh();
    void healthMetrics.refresh();
    void systemMonitor.refresh();
    void fetchState()
      .then((snapshot) => setAssistantState(snapshot.state))
      .catch(() => {
        /* keep last known */
      });
    if (
      previous === 'DISCONNECTED' ||
      previous === 'RECONNECTING' ||
      previous === 'ERROR'
    ) {
      publishAnnouncement('Connection restored', 'polite');
    }
  }, [
    socket.connectionStatus,
    voice.refresh,
    speech.refresh,
    workspace.refresh,
    healthMetrics.refresh,
    systemMonitor.refresh,
    publishAnnouncement,
  ]);

  useEffect(() => {
    return () => {
      if (announceTimer.current) window.clearTimeout(announceTimer.current);
    };
  }, []);

  const activity: ActivityEntry[] = useMemo(
    () =>
      timeline.map((item) => ({
        id: item.id,
        timestamp: item.timestamp,
        message: item.message,
      })),
    [timeline],
  );

  const value = useMemo<DashboardContextValue>(
    () => ({
      connectionStatus: socket.connectionStatus,
      assistantState,
      dataStale,
      connectedAt,
      health: healthMetrics.health,
      healthError: healthMetrics.error,
      metricHistory: healthMetrics.history,
      refreshHealth: healthMetrics.refresh,
      timeline,
      clearTimeline,
      activity,
      announcement,
      tabVisible,
      reducedMotion,
      reducedMotionOverride,
      setReducedMotionOverride,
      voice,
      speech,
      workspace,
      systemMonitor,
    }),
    [
      socket.connectionStatus,
      assistantState,
      dataStale,
      connectedAt,
      healthMetrics.health,
      healthMetrics.error,
      healthMetrics.history,
      healthMetrics.refresh,
      timeline,
      clearTimeline,
      activity,
      announcement,
      tabVisible,
      reducedMotion,
      reducedMotionOverride,
      voice,
      speech,
      workspace,
      systemMonitor,
    ],
  );

  return (
    <DashboardContext.Provider value={value}>{children}</DashboardContext.Provider>
  );
}

export function useDashboard(): DashboardContextValue {
  const ctx = useContext(DashboardContext);
  if (!ctx) {
    throw new Error('useDashboard must be used within DashboardProvider');
  }
  return ctx;
}
