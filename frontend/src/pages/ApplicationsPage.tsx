import styles from './ApplicationsPage.module.css';

const APPS = [
  { name: 'VS Code', initials: 'VS' },
  { name: 'Chrome', initials: 'CH' },
  { name: 'Gmail', initials: 'GM' },
  { name: 'Microsoft Teams', initials: 'MT' },
  { name: 'WhatsApp', initials: 'WA' },
  { name: 'Spotify', initials: 'SP' },
  { name: 'News', initials: 'NW' },
];

export function ApplicationsPage() {
  return (
    <div className={styles.page}>
      <header>
        <h1 className="page-title">APPLICATIONS</h1>
        <p className="page-subtitle">Workspace targets</p>
      </header>

      <div className={styles.grid}>
        {APPS.map((app) => (
          <article key={app.name} className={`glass-panel ${styles.tile}`}>
            <div className={styles.icon} aria-hidden="true">
              {app.initials}
            </div>
            <h2 className={styles.name}>{app.name}</h2>
            <p className={styles.status}>Not connected</p>
            <p className="placeholder-note">
              Application control will be added in a later phase
            </p>
          </article>
        ))}
      </div>
    </div>
  );
}
