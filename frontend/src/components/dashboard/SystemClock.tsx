import { useEffect, useState } from 'react';

import { CLOCK_HOUR12 } from '../../types/dashboard';
import styles from './SystemClock.module.css';

export function SystemClock() {
  const [now, setNow] = useState(() => new Date());

  useEffect(() => {
    const id = window.setInterval(() => setNow(new Date()), 1000);
    return () => window.clearInterval(id);
  }, []);

  const time = new Intl.DateTimeFormat(undefined, {
    hour: 'numeric',
    minute: '2-digit',
    second: '2-digit',
    hour12: CLOCK_HOUR12,
  }).format(now);

  const day = new Intl.DateTimeFormat(undefined, { weekday: 'long' }).format(now);
  const date = new Intl.DateTimeFormat(undefined, {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  }).format(now);

  return (
    <div className={styles.clock} aria-live="off">
      <span className={styles.time}>{time}</span>
      <span className={styles.meta}>
        {day} · {date}
      </span>
    </div>
  );
}
