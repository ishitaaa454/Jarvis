import type { MetricHistoryState, MetricSample } from '../types/dashboard';

export const DEFAULT_METRIC_CAPACITY = 90;

export type MetricHistoryAction =
  | { type: 'push'; sample: MetricSample }
  | { type: 'reset'; capacity?: number };

export function createMetricHistory(
  capacity = DEFAULT_METRIC_CAPACITY,
): MetricHistoryState {
  return { samples: [], capacity };
}

export function metricHistoryReducer(
  state: MetricHistoryState,
  action: MetricHistoryAction,
): MetricHistoryState {
  switch (action.type) {
    case 'reset':
      return createMetricHistory(action.capacity ?? state.capacity);
    case 'push': {
      const next = [...state.samples, action.sample];
      if (next.length > state.capacity) {
        next.splice(0, next.length - state.capacity);
      }
      return { ...state, samples: next };
    }
    default:
      return state;
  }
}

export function metricBounds(values: number[]): { min: number; max: number } {
  if (values.length === 0) return { min: 0, max: 0 };
  let min = values[0];
  let max = values[0];
  for (const value of values) {
    if (!Number.isFinite(value)) continue;
    if (value < min) min = value;
    if (value > max) max = value;
  }
  return { min, max };
}
