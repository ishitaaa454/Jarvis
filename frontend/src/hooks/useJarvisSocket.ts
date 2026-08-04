import { useEffect, useRef, useState } from 'react';

import { environment } from '../config/environment';
import { JarvisSocket } from '../services/websocket';
import type { AssistantState, ConnectionStatus } from '../types/assistant';
import type { ActivityEntry, StateChangedPayload, WebSocketMessage } from '../types/messages';

function createActivity(message: string, timestamp?: string): ActivityEntry {
  return {
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    timestamp: timestamp ?? new Date().toISOString(),
    message,
  };
}

export interface UseJarvisSocketResult {
  connectionStatus: ConnectionStatus;
  assistantState: AssistantState | null;
  activity: ActivityEntry[];
}

export function useJarvisSocket(): UseJarvisSocketResult {
  const [connectionStatus, setConnectionStatus] =
    useState<ConnectionStatus>('CONNECTING');
  const [assistantState, setAssistantState] = useState<AssistantState | null>(null);
  const [activity, setActivity] = useState<ActivityEntry[]>([]);
  const socketRef = useRef<JarvisSocket | null>(null);

  useEffect(() => {
    let active = true;

    const pushActivity = (message: string, timestamp?: string) => {
      if (!active) return;
      setActivity((prev) => {
        const next = [createActivity(message, timestamp), ...prev];
        return next.slice(0, environment.maxActivityEntries);
      });
    };

    const handleMessage = (message: WebSocketMessage) => {
      if (message.type === 'connection.established') {
        const text =
          typeof message.payload.message === 'string'
            ? message.payload.message
            : 'Connected to Jarvis backend';
        pushActivity(text, message.timestamp);
        return;
      }

      if (message.type === 'state.changed') {
        const payload = message.payload as unknown as StateChangedPayload;
        setAssistantState(payload.state as AssistantState);
        pushActivity(
          `State → ${payload.state}${
            payload.previous_state ? ` (from ${payload.previous_state})` : ''
          }`,
          message.timestamp,
        );
      }
    };

    const handleStatus = (status: 'open' | 'closed' | 'error') => {
      if (!active) return;
      if (status === 'open') {
        setConnectionStatus('CONNECTED');
        return;
      }
      if (status === 'error') {
        setConnectionStatus((prev) =>
          prev === 'CONNECTED' ? 'RECONNECTING' : 'ERROR',
        );
        return;
      }
      setConnectionStatus((prev) => {
        if (prev === 'CONNECTING') return 'RECONNECTING';
        return prev === 'CONNECTED' ? 'RECONNECTING' : 'DISCONNECTED';
      });
      pushActivity('WebSocket disconnected — attempting reconnect');
    };

    setConnectionStatus('CONNECTING');
    const socket = new JarvisSocket({
      url: environment.wsUrl,
      onMessage: handleMessage,
      onStatus: handleStatus,
    });
    socketRef.current = socket;
    socket.connect();

    return () => {
      active = false;
      socket.disconnect();
      socketRef.current = null;
    };
  }, []);

  return { connectionStatus, assistantState, activity };
}
