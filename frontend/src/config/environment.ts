const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8765';
const wsUrl = import.meta.env.VITE_WS_URL ?? 'ws://127.0.0.1:8765/ws';

export const environment = {
  apiBaseUrl,
  wsUrl,
  healthPollIntervalMs: 5000,
  maxActivityEntries: 40,
} as const;
