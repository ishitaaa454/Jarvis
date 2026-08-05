import { useDashboard } from '../../context/DashboardContext';
import styles from './ActivityTimeline.module.css';

export function ActivityTimeline() {
  const { timeline, clearTimeline } = useDashboard();

  return (
    <section className={styles.panel} aria-label="Activity timeline">
      <header className={styles.header}>
        <h2>Activity</h2>
        <button type="button" className={styles.clear} onClick={clearTimeline} data-no-swipe>
          Clear
        </button>
      </header>
      {timeline.length === 0 ? (
        <p className={styles.empty}>Awaiting system events</p>
      ) : (
        <ol className={styles.list}>
          {timeline.slice(0, 24).map((item) => {
            const time = new Intl.DateTimeFormat(undefined, {
              hour: 'numeric',
              minute: '2-digit',
              second: '2-digit',
            }).format(new Date(item.timestamp));
            return (
              <li
                key={item.id}
                className={`${styles.item} ${styles[item.severity.toLowerCase()]}`}
              >
                <div className={styles.meta}>
                  <span>{time}</span>
                  <span>{item.category}</span>
                </div>
                <p>{item.message}</p>
                {item.progress && (
                  <span className={styles.progress}>
                    {item.progress.completed}/{item.progress.total}
                  </span>
                )}
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
}
