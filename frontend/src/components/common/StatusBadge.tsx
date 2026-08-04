import styles from './StatusBadge.module.css';

interface StatusBadgeProps {
  label: string;
  value: string;
  tone?: 'neutral' | 'accent' | 'warning' | 'danger';
}

export function StatusBadge({
  label,
  value,
  tone = 'neutral',
}: StatusBadgeProps) {
  return (
    <div className={`${styles.badge} ${styles[tone]}`}>
      <span className={styles.label}>{label}</span>
      <strong className={styles.value}>{value}</strong>
    </div>
  );
}
