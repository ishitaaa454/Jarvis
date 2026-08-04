export type AssistantState =
  | 'OFFLINE'
  | 'STARTING'
  | 'IDLE'
  | 'LISTENING'
  | 'PROCESSING'
  | 'SPEAKING'
  | 'INITIALIZING_WORKSPACE'
  | 'OPENING_APPLICATIONS'
  | 'READY'
  | 'ERROR'
  | 'SHUTTING_DOWN';

export type ConnectionStatus =
  | 'CONNECTING'
  | 'CONNECTED'
  | 'DISCONNECTED'
  | 'RECONNECTING'
  | 'ERROR';

export interface AssistantStateSnapshot {
  state: AssistantState;
  previous_state: AssistantState | null;
  changed_at: string;
}

export interface SystemMetrics {
  platform: string;
  cpu_percent: number;
  memory_percent: number;
}

export interface HealthResponse {
  status: string;
  service: string;
  version: string;
  timestamp: string;
  system: SystemMetrics;
}
