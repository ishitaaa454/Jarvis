import styles from './MetricLineChart.module.css';
import type { HistoryPoint } from '../../types/systemMonitor';

interface Props {
  label: string;
  points: HistoryPoint[];
  unit?: string;
  reducedMotion?: boolean;
}

export function MetricLineChart({ label, points, unit = '', reducedMotion = false }: Props) {
  const values = points.map((p) => p.value).filter((v): v is number => v != null && Number.isFinite(v));
  const width = 240;
  const height = 64;
  let path = '';
  let summary = `${label}: no samples`;

  if (values.length === 0) {
    path = `M0 ${height / 2} H${width}`;
  } else if (values.length === 1 || Math.max(...values) === Math.min(...values)) {
    const y = height / 2;
    path = `M0 ${y} H${width}`;
    summary = `${label}: constant ${values[0].toFixed(1)}${unit}`;
  } else {
    const min = Math.min(...values);
    const max = Math.max(...values);
    const range = max - min || 1;
    const coords = values.map((value, index) => {
      const x = (index / (values.length - 1)) * width;
      const y = height - ((value - min) / range) * (height - 8) - 4;
      return `${x.toFixed(2)},${y.toFixed(2)}`;
    });
    path = `M${coords.join(' L')}`;
    summary = `${label}: ${values[values.length - 1].toFixed(1)}${unit}, range ${min.toFixed(1)}–${max.toFixed(1)}${unit}`;
  }

  return (
    <div className={styles.wrap}>
      <svg
        className={`${styles.svg} ${reducedMotion ? styles.static : ''}`}
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label={summary}
      >
        <path d={path} className={styles.line} fill="none" />
      </svg>
      <p className={styles.caption}>LIVE SESSION HISTORY</p>
    </div>
  );
}
