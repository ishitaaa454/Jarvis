import type { WebSocketMessage } from '../types/messages';

export type SocketMessageHandler = (message: WebSocketMessage) => void;
export type SocketStatusHandler = (status: 'open' | 'closed' | 'error') => void;

export interface JarvisSocketOptions {
  url: string;
  onMessage: SocketMessageHandler;
  onStatus: SocketStatusHandler;
  maxReconnectDelayMs?: number;
}

/**
 * Thin WebSocket client with capped exponential reconnect.
 * Ownership of connect/disconnect lifecycle stays with the React hook.
 */
export class JarvisSocket {
  private socket: WebSocket | null = null;
  private intentionalClose = false;
  private reconnectAttempt = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private readonly maxReconnectDelayMs: number;

  constructor(private readonly options: JarvisSocketOptions) {
    this.maxReconnectDelayMs = options.maxReconnectDelayMs ?? 10000;
  }

  connect(): void {
    this.intentionalClose = false;
    this.clearReconnectTimer();

    if (
      this.socket &&
      (this.socket.readyState === WebSocket.OPEN ||
        this.socket.readyState === WebSocket.CONNECTING)
    ) {
      return;
    }

    const socket = new WebSocket(this.options.url);
    this.socket = socket;

    socket.onopen = () => {
      this.reconnectAttempt = 0;
      this.options.onStatus('open');
    };

    socket.onmessage = (event: MessageEvent<string>) => {
      try {
        const parsed = JSON.parse(event.data) as WebSocketMessage;
        this.options.onMessage(parsed);
      } catch {
        // Ignore malformed frames in Phase 1.
      }
    };

    socket.onerror = () => {
      this.options.onStatus('error');
    };

    socket.onclose = () => {
      this.options.onStatus('closed');
      this.socket = null;
      if (!this.intentionalClose) {
        this.scheduleReconnect();
      }
    };
  }

  disconnect(): void {
    this.intentionalClose = true;
    this.clearReconnectTimer();
    if (this.socket) {
      this.socket.close();
      this.socket = null;
    }
  }

  private scheduleReconnect(): void {
    this.clearReconnectTimer();
    const delay = Math.min(
      1000 * 2 ** this.reconnectAttempt,
      this.maxReconnectDelayMs,
    );
    this.reconnectAttempt += 1;
    this.reconnectTimer = setTimeout(() => this.connect(), delay);
  }

  private clearReconnectTimer(): void {
    if (this.reconnectTimer !== null) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }
}
