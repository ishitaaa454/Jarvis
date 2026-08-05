import { metricBounds } from '../../reducers/metricHistoryReducer';
import styles from './CircularMetric.module.css';

interface Props {
  label: string;
  value: number | null;
  history: number[];
  unit?: string;
}

export function CircularMetric({ label, value, history, unit = '%' }: Props) {
  const safe = Number.isFinite(value ?? NaN) ? Number(value) : null;
  const ratio = safe == null ? 0 : Math.max(0, Math.min(100, safe)) / 100;
  const radius = 42;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - ratio);
  const { min, max } = metricBounds(history.filter((n) => Number.isFinite(n)));
  const spark = buildSparkline(history);

  return (
    <div className={styles.card} data-no-swipe>
      <div className={styles.top}>
        <svg viewBox="0 0 100 100" className={styles.ring} aria-hidden="true">
          <circle cx="50" cy="50" r={radius} className={styles.track} />
          <circle
            cx="50"
            cy="50"
            r={radius}
            className={styles.valueRing}
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            transform="rotate(-90 50 50)"
          />
          <text x="50" y="54" textAnchor="middle" className={styles.valueText}>
            {safe == null ? '—' : `${Math.round(safe)}${unit}`}
          </text>
        </svg>
        <div>
          <p className={styles.label}>{label}</p>
          <p className={styles.sub}>LIVE SESSION HISTORY</p>
          <p className={styles.bounds}>
            Min {history.length ? Math.round(min) : '—'}
            {unit} · Max {history.length ? Math.round(max) : '—'}
            {unit}
          </p>
        </div>
      </div>
      <svg className={styles.spark} viewBox="0 0 120 36" role="img" aria-label={`${label} session sparkline`}>
        {spark}
      </svg>
    </div>
  );
}

function buildSparkline(values: number[]) {
  const clean = values.filter((n) => Number.isFinite(n));
  if (clean.length === 0) {
    return <path d="M0 18 H120" className={styles.sparkEmpty} />;
  }
  if (clean.length === 1 || metricBounds(clean).max === metricBounds(clean).min) {
    return <path d="M0 18 H120" className={styles.sparkLine} />;
  }
  const { min, max } = metricBounds(clean);
  const range = max - min || 1;
  const points = clean.map((value, index) => {
    const x = (index / (clean.length - 1)) * 120;
    const y = 32 - ((value - min) / range) * 28;
    return `${x.toFixed(2)},${y.toFixed(2)}`;
  });
  return <polyline points={points.join(' ')} className={styles.sparkLine} fill="none" />;
}
