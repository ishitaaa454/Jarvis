import type { ConnectionStatus } from '../../types/assistant';
import styles from './ConnectionIndicator.module.css';

interface ConnectionIndicatorProps {
  status: ConnectionStatus;
}

const STATUS_CLASS: Record<ConnectionStatus, string> = {
  CONNECTING: styles.connecting,
  CONNECTED: styles.connected,
  DISCONNECTED: styles.disconnected,
  RECONNECTING: styles.reconnecting,
  ERROR: styles.error,
};

export function ConnectionIndicator({ status }: ConnectionIndicatorProps) {
  return (
    <div className={`${styles.badge} ${STATUS_CLASS[status]}`}>
      <span className={styles.dot} aria-hidden="true" />
      <span>{status}</span>
    </div>
  );
}
