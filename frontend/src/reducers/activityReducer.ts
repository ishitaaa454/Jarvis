import type { TimelineEntry } from '../types/dashboard';

export const MAX_TIMELINE_ENTRIES = 80;

export type ActivityAction =
  | { type: 'append'; entry: TimelineEntry }
  | { type: 'clear' }
  | { type: 'replace'; entries: TimelineEntry[] };

function severityRank(severity: TimelineEntry['severity']): number {
  switch (severity) {
    case 'ERROR':
      return 3;
    case 'WARNING':
      return 2;
    case 'SUCCESS':
      return 1;
    default:
      return 0;
  }
}

/** Keep important errors longer when trimming the timeline. */
export function trimTimeline(
  entries: TimelineEntry[],
  capacity = MAX_TIMELINE_ENTRIES,
): TimelineEntry[] {
  if (entries.length <= capacity) return entries;
  const errors = entries.filter((e) => e.severity === 'ERROR');
  const rest = entries.filter((e) => e.severity !== 'ERROR');
  const keepErrors = errors.slice(0, Math.min(20, capacity));
  const keepRest = rest.slice(0, Math.max(0, capacity - keepErrors.length));
  return [...keepErrors, ...keepRest]
    .sort((a, b) => {
      const byTime = b.timestamp.localeCompare(a.timestamp);
      if (byTime !== 0) return byTime;
      return severityRank(b.severity) - severityRank(a.severity);
    })
    .slice(0, capacity);
}

export function activityReducer(
  state: TimelineEntry[],
  action: ActivityAction,
): TimelineEntry[] {
  switch (action.type) {
    case 'clear':
      return [];
    case 'replace':
      return trimTimeline(action.entries);
    case 'append': {
      if (state.some((item) => item.id === action.entry.id)) {
        return state;
      }
      return trimTimeline([action.entry, ...state]);
    }
    default:
      return state;
  }
}

export function makeTimelineId(
  type: string,
  timestamp: string,
  detail: string,
): string {
  return `${type}|${timestamp}|${detail}`;
}
