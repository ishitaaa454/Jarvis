import styles from './MetricUnavailable.module.css';

interface Props {
  title: string;
  reason?: string | null;
  onRetry?: () => void;
}

export function MetricUnavailable({ title, reason, onRetry }: Props) {
  return (
    <div className={styles.card} role="status">
      <strong>{title}</strong>
      <p>{reason ?? 'UNAVAILABLE'}</p>
      {onRetry ? (
        <button type="button" onClick={onRetry} data-no-swipe>
          Retry
        </button>
      ) : null}
    </div>
  );
}
