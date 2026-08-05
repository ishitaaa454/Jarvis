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
  pushActivity: (message: string, timestamp?: string) => void;
  registerMessageHandler: (handler: ((message: WebSocketMessage) => void) | null) => void;
}

export function useJarvisSocket(): UseJarvisSocketResult {
  const [connectionStatus, setConnectionStatus] =
    useState<ConnectionStatus>('CONNECTING');
  const [assistantState, setAssistantState] = useState<AssistantState | null>(null);
  const [activity, setActivity] = useState<ActivityEntry[]>([]);
  const socketRef = useRef<JarvisSocket | null>(null);
  const externalHandlerRef = useRef<((message: WebSocketMessage) => void) | null>(null);

  const pushActivity = (message: string, timestamp?: string) => {
    setActivity((prev) => {
      const next = [createActivity(message, timestamp), ...prev];
      return next.slice(0, environment.maxActivityEntries);
    });
  };

  const registerMessageHandler = (
    handler: ((message: WebSocketMessage) => void) | null,
  ) => {
    externalHandlerRef.current = handler;
  };

  useEffect(() => {
    let active = true;

    const push = (message: string, timestamp?: string) => {
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
        push(text, message.timestamp);
      } else if (message.type === 'state.changed') {
        const payload = message.payload as unknown as StateChangedPayload;
        setAssistantState(payload.state as AssistantState);
        push(
          `State → ${payload.state}${
            payload.previous_state ? ` (from ${payload.previous_state})` : ''
          }`,
          message.timestamp,
        );
      } else if (message.type === 'voice.wake_detected') {
        push('Wake phrase detected', message.timestamp);
      } else if (message.type === 'assistant.activation_started') {
        push('Microphone paused', message.timestamp);
        push('Welcome sequence started', message.timestamp);
      } else if (message.type === 'tts.utterance_started') {
        const index = Number(message.payload.index ?? 0);
        const total = Number(message.payload.total ?? 3);
        push(`Speaking welcome message ${index} of ${total}`, message.timestamp);
      } else if (message.type === 'tts.sequence_finished') {
        push('Welcome sequence complete', message.timestamp);
      } else if (message.type === 'assistant.activation_finished') {
        push('Wake listener resumed', message.timestamp);
      } else if (message.type === 'assistant.workspace_initialization_started') {
        push('Workspace initialization started', message.timestamp);
      } else if (message.type === 'workspace.run_started') {
        const total = Number(message.payload.total ?? 0);
        push(`Workspace launch started (${total} application${total === 1 ? '' : 's'})`, message.timestamp);
      } else if (message.type === 'workspace.application_status') {
        const status = String(message.payload.status ?? '');
        const displayName = String(message.payload.display_name ?? 'Application');
        if (status === 'LAUNCHING') {
          push(`Launching ${displayName}`, message.timestamp);
        } else if (status === 'RESTORING' || status === 'ALREADY_RUNNING') {
          push(`Restoring ${displayName}`, message.timestamp);
        }
      } else if (message.type === 'workspace.application_result') {
        const displayName = String(message.payload.display_name ?? 'Application');
        const result = String(message.payload.result ?? '');
        if (result === 'FAILED') {
          push(`${displayName} failed to open`, message.timestamp);
        } else if (result === 'ALREADY_RUNNING') {
          push(`${displayName} was already running`, message.timestamp);
        } else if (result === 'LAUNCHED') {
          push(`${displayName} launched`, message.timestamp);
        }
      } else if (message.type === 'assistant.workspace_ready') {
        push('Workspace ready', message.timestamp);
      } else if (message.type === 'workspace.run_finished') {
        const status = String(message.payload.status ?? '');
        if (status === 'PARTIAL_SUCCESS') {
          push('Workspace launch finished (partially ready)', message.timestamp);
        } else if (status === 'ERROR') {
          push('Workspace launch failed', message.timestamp);
        } else if (status === 'READY') {
          push('Workspace launch finished', message.timestamp);
        }
      } else if (message.type === 'workspace.run_cancelled') {
        push('Workspace launch cancelled', message.timestamp);
      } else if (message.type === 'workspace.error') {
        const text = typeof message.payload.message === 'string' ? message.payload.message : 'Workspace error';
        push(`Workspace error: ${text}`, message.timestamp);
      }

      externalHandlerRef.current?.(message);
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
      push('WebSocket disconnected — attempting reconnect');
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

  return {
    connectionStatus,
    assistantState,
    activity,
    pushActivity,
    registerMessageHandler,
  };
}
