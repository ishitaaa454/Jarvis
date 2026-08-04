export interface WebSocketMessage<T = Record<string, unknown>> {
  type: string;
  timestamp: string;
  payload: T;
}

export interface ConnectionEstablishedPayload {
  message: string;
}

export interface StateChangedPayload {
  state: string;
  previous_state: string | null;
  changed_at: string;
}

export interface ActivityEntry {
  id: string;
  timestamp: string;
  message: string;
}
