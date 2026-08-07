import { makeTimelineId } from '../reducers/activityReducer';
import type { AssistantState } from '../types/assistant';
import type { TimelineEntry } from '../types/dashboard';
import type { WebSocketMessage } from '../types/messages';

export interface DispatchedEventEffects {
  assistantState?: AssistantState;
  timeline?: TimelineEntry;
  announcement?: { message: string; politeness: 'polite' | 'assertive' };
  markLive?: boolean;
}

function entry(
  type: string,
  timestamp: string,
  detail: string,
  category: TimelineEntry['category'],
  severity: TimelineEntry['severity'],
  message: string,
  extra?: Partial<TimelineEntry>,
): TimelineEntry {
  return {
    id: makeTimelineId(type, timestamp, detail),
    timestamp,
    category,
    severity,
    message,
    ...extra,
  };
}

/** Central WebSocket → dashboard effects. Domain hooks still receive the raw message. */
export function dispatchDashboardEvent(
  message: WebSocketMessage,
): DispatchedEventEffects {
  const ts = message.timestamp || new Date().toISOString();
  const p = message.payload ?? {};

  switch (message.type) {
    case 'connection.established': {
      const text =
        typeof p.message === 'string' ? p.message : 'Connected to Jarvis backend';
      return {
        timeline: entry(message.type, ts, text, 'CONNECTION', 'SUCCESS', text),
        announcement: { message: 'Backend connected', politeness: 'polite' },
        markLive: true,
      };
    }
    case 'state.changed': {
      const state = String(p.state ?? '') as AssistantState;
      const previous = p.previous_state ? String(p.previous_state) : null;
      return {
        assistantState: state,
        timeline: entry(
          message.type,
          ts,
          state,
          'SYSTEM',
          state === 'ERROR' ? 'ERROR' : 'INFO',
          `State → ${state}${previous ? ` (from ${previous})` : ''}`,
        ),
      };
    }
    case 'voice.wake_detected':
      return {
        timeline: entry(message.type, ts, 'wake', 'VOICE', 'SUCCESS', 'Wake phrase detected'),
        announcement: { message: 'Voice activation confirmed', politeness: 'assertive' },
      };
    case 'assistant.activation_started':
      return {
        timeline: entry(
          message.type,
          ts,
          'activation',
          'SPEECH',
          'INFO',
          'Welcome sequence started',
        ),
      };
    case 'tts.utterance_started': {
      const index = Number(p.index ?? 0);
      const total = Number(p.total ?? 3);
      return {
        timeline: entry(
          message.type,
          ts,
          `${index}/${total}`,
          'SPEECH',
          'INFO',
          `Speaking message ${index} of ${total}`,
          { progress: { completed: index, total } },
        ),
        announcement:
          index === 1
            ? { message: 'Jarvis speaking', politeness: 'polite' }
            : undefined,
      };
    }
    case 'tts.sequence_finished':
      return {
        timeline: entry(
          message.type,
          ts,
          'finished',
          'SPEECH',
          'SUCCESS',
          'Welcome sequence complete',
        ),
      };
    case 'tts.sequence_cancelled':
      return {
        timeline: entry(
          message.type,
          ts,
          'cancelled',
          'SPEECH',
          'WARNING',
          'Welcome sequence cancelled',
        ),
      };
    case 'tts.error':
    case 'voice.error':
    case 'workspace.error': {
      const err =
        typeof p.message === 'string'
          ? p.message
          : typeof p.error === 'string'
            ? p.error
            : 'Service error';
      return {
        timeline: entry(message.type, ts, err, 'ERROR', 'ERROR', err),
        announcement: { message: err, politeness: 'assertive' },
      };
    }
    case 'assistant.activation_finished':
      return {
        timeline: entry(
          message.type,
          ts,
          'resume',
          'VOICE',
          'INFO',
          'Wake listener resumed',
        ),
      };
    case 'assistant.workspace_initialization_started':
      return {
        timeline: entry(
          message.type,
          ts,
          'ws-init',
          'WORKSPACE',
          'INFO',
          'Workspace initialization started',
        ),
        announcement: { message: 'Workspace initialization started', politeness: 'polite' },
      };
    case 'workspace.run_started': {
      const total = Number(p.total_applications ?? p.total ?? 0);
      return {
        timeline: entry(
          message.type,
          ts,
          String(p.run_id ?? total),
          'WORKSPACE',
          'INFO',
          `Workspace launch started (${total} application${total === 1 ? '' : 's'})`,
          { progress: { completed: 0, total } },
        ),
        announcement: { message: 'Opening workspace', politeness: 'polite' },
      };
    }
    case 'workspace.application_status': {
      const status = String(p.status ?? '');
      const displayName = String(p.display_name ?? 'Application');
      const appId = typeof p.application_id === 'string' ? p.application_id : undefined;
      const index = Number(p.index ?? 0);
      const total = Number(p.total ?? 0);
      let line = `${displayName}: ${status}`;
      if (status === 'LAUNCHING') line = `Launching ${displayName}`;
      else if (status === 'RESTORING') line = `Restoring ${displayName}`;
      else if (status === 'ALREADY_RUNNING' || status === 'CHECKING') {
        line = `Checking ${displayName}`;
      } else if (status === 'OPENING_URL' || status === 'OPENING') {
        line = `Opening ${displayName}`;
      }
      return {
        timeline: entry(
          message.type,
          ts,
          `${appId ?? displayName}|${status}`,
          'APPLICATION',
          'INFO',
          line,
          {
            applicationId: appId,
            progress: total > 0 ? { completed: index, total } : undefined,
          },
        ),
      };
    }
    case 'workspace.application_result': {
      const displayName = String(p.display_name ?? 'Application');
      const result = String(p.result ?? '');
      const appId = typeof p.application_id === 'string' ? p.application_id : undefined;
      const failed = result === 'FAILED';
      let line = `${displayName}: ${result}`;
      if (result === 'FAILED') line = `${displayName} failed to open`;
      else if (result === 'ALREADY_RUNNING') line = `${displayName} was already running`;
      else if (result === 'LAUNCHED') line = `${displayName} launched`;
      else if (result === 'RESTORED') line = `${displayName} restored`;
      else if (result === 'OPENED') line = `${displayName} opened`;
      return {
        timeline: entry(
          message.type,
          ts,
          `${appId ?? displayName}|${result}`,
          'APPLICATION',
          failed ? 'ERROR' : 'SUCCESS',
          line,
          { applicationId: appId },
        ),
      };
    }
    case 'assistant.workspace_ready':
      return {
        timeline: entry(
          message.type,
          ts,
          'ready',
          'WORKSPACE',
          'SUCCESS',
          'Workspace ready',
        ),
        announcement: { message: 'Workspace ready', politeness: 'polite' },
      };
    case 'workspace.run_finished': {
      const status = String(p.status ?? '');
      const severity =
        status === 'ERROR' ? 'ERROR' : status === 'PARTIAL_SUCCESS' ? 'WARNING' : 'SUCCESS';
      const line =
        status === 'PARTIAL_SUCCESS'
          ? 'Workspace launch finished (partially ready)'
          : status === 'ERROR'
            ? 'Workspace launch failed'
            : 'Workspace launch finished';
      return {
        timeline: entry(message.type, ts, status, 'WORKSPACE', severity, line),
      };
    }
    case 'workspace.run_cancelled':
      return {
        timeline: entry(
          message.type,
          ts,
          'cancelled',
          'WORKSPACE',
          'WARNING',
          'Workspace launch cancelled',
        ),
      };
    case 'workspace.warning': {
      const msg = typeof p.message === 'string' ? p.message : 'Workspace warning';
      return {
        timeline: entry(message.type, ts, msg, 'WORKSPACE', 'WARNING', msg),
      };
    }
    case 'voice.status_changed':
    case 'tts.status_changed':
    case 'workspace.status_changed':
    case 'tts.utterance_finished':
    case 'tts.sequence_started':
    case 'system.metrics':
      return {};
    case 'system.monitor_status': {
      const status = String(p.status ?? '');
      if (status === 'RUNNING' || status === 'DEGRADED' || status === 'STOPPED') {
        return {
          timeline: entry(
            message.type,
            ts,
            status,
            'SYSTEM',
            status === 'DEGRADED' ? 'WARNING' : 'INFO',
            `System monitor ${status.toLowerCase()}`,
          ),
        };
      }
      return {};
    }
    case 'system.capabilities_changed':
      return {
        timeline: entry(
          message.type,
          ts,
          'caps',
          'SYSTEM',
          'INFO',
          'System monitoring capabilities updated',
        ),
      };
    case 'system.monitor_warning': {
      const msg = typeof p.message === 'string' ? p.message : 'System monitor warning';
      return {
        timeline: entry(message.type, ts, msg, 'SYSTEM', 'WARNING', msg),
      };
    }
    case 'system.monitor_error': {
      const msg = typeof p.message === 'string' ? p.message : 'System monitor error';
      return {
        timeline: entry(message.type, ts, msg, 'ERROR', 'ERROR', msg),
        announcement: { message: msg, politeness: 'assertive' },
      };
    }
    case 'system.processes_updated':
    case 'windows.inventory_changed':
    case 'windows.foreground_changed':
      return {};
    case 'hotkey.status_changed': {
      const status = String(p.status ?? '');
      if (status === 'REGISTERED' || status === 'CONFLICT' || status === 'ERROR') {
        return {
          timeline: entry(
            message.type,
            ts,
            status,
            'SYSTEM',
            status === 'REGISTERED' ? 'SUCCESS' : 'WARNING',
            status === 'REGISTERED'
              ? 'Global Jarvis shortcut registered'
              : `Global shortcut ${status.toLowerCase()}`,
          ),
        };
      }
      return {};
    }
    case 'hotkey.triggered':
      return {
        timeline: entry(
          message.type,
          ts,
          'show-dashboard',
          'SYSTEM',
          'INFO',
          'Returned to dashboard (Ctrl+Alt+J)',
        ),
      };
    case 'browser.status_changed':
      return {};
    case 'browser.destination_opened': {
      const id = String(p.id ?? 'destination');
      return {
        timeline: entry(
          message.type,
          ts,
          id,
          'APPLICATION',
          'SUCCESS',
          `${id} destination opened`,
        ),
      };
    }
    case 'browser.destination_focused': {
      const id = String(p.id ?? 'destination');
      return {
        timeline: entry(
          message.type,
          ts,
          `${id}-focus`,
          'APPLICATION',
          'INFO',
          `${id} destination focused`,
        ),
      };
    }
    case 'browser.destination_unavailable':
      return {
        timeline: entry(
          message.type,
          ts,
          String(p.id ?? 'dest'),
          'APPLICATION',
          'WARNING',
          'Browser destination unavailable',
        ),
      };
    default:
      if (import.meta.env.DEV) {
        console.warn(`[dashboard] Unknown WebSocket event: ${message.type}`);
      }
      return {};
  }
}
