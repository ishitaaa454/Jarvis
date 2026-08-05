import { useCallback, useEffect, useReducer, useRef, useState } from 'react';

import { environment } from '../config/environment';
import {
  createMetricHistory,
  metricHistoryReducer,
} from '../reducers/metricHistoryReducer';
import { fetchHealth } from '../services/api';
import type { HealthResponse } from '../types/assistant';

export function useHealthMetrics() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [history, dispatchHistory] = useReducer(
    metricHistoryReducer,
    undefined,
    () => createMetricHistory(),
  );
  const mounted = useRef(true);

  const refresh = useCallback(async () => {
    try {
      const data = await fetchHealth();
      if (!mounted.current) return;
      setHealth(data);
      setError(null);
      dispatchHistory({
        type: 'push',
        sample: {
          timestamp: Date.now(),
          cpuPercent: data.system.cpu_percent,
          memoryPercent: data.system.memory_percent,
        },
      });
    } catch (err) {
      if (!mounted.current) return;
      setError(err instanceof Error ? err.message : 'Health request failed');
    }
  }, []);

  useEffect(() => {
    mounted.current = true;
    void refresh();
    const id = window.setInterval(() => void refresh(), environment.healthPollIntervalMs);
    return () => {
      mounted.current = false;
      window.clearInterval(id);
    };
  }, [refresh]);

  return { health, error, history, refresh };
}
