import styles from './MetricCard.module.css';

interface MetricCardProps {
  title: string;
  value: string | null;
  unit?: string;
  loading?: boolean;
  error?: string | null;
  placeholder?: string;
}

export function MetricCard({
  title,
  value,
  unit,
  loading = false,
  error = null,
  placeholder,
}: MetricCardProps) {
  let body: string;
  if (error) {
    body = error;
  } else if (loading) {
    body = 'Loading…';
  } else if (value === null || value === undefined) {
    body = '—';
  } else {
    body = unit ? `${value}${unit}` : value;
  }

  return (
    <article className={`glass-panel ${styles.card}`}>
      <h3 className={styles.title}>{title}</h3>
      <p className={`${styles.value} ${error ? 'error-text' : ''}`}>{body}</p>
      {placeholder && value === null && !loading && !error ? (
        <p className="placeholder-note">{placeholder}</p>
      ) : null}
    </article>
  );
}
