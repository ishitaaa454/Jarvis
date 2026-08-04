import type { ActivityEntry } from '../../types/messages';
import styles from './ActivityLog.module.css';

interface ActivityLogProps {
  entries: ActivityEntry[];
}

export function ActivityLog({ entries }: ActivityLogProps) {
  return (
    <section className={`glass-panel ${styles.panel}`}>
      <h3 className={styles.title}>Recent Activity</h3>
      {entries.length === 0 ? (
        <p className="muted">No activity yet. Waiting for backend events…</p>
      ) : (
        <ul className={styles.list}>
          {entries.map((entry) => (
            <li key={entry.id} className={styles.item}>
              <time dateTime={entry.timestamp}>
                {new Date(entry.timestamp).toLocaleTimeString()}
              </time>
              <span>{entry.message}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
