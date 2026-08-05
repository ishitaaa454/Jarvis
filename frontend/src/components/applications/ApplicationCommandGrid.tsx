import { useDashboard } from '../../context/DashboardContext';
import type { ApplicationRuntimeStatus } from '../../types/workspace';
import styles from './ApplicationCommandGrid.module.css';

const INITIALS: Record<string, string> = {
  vscode: 'VS',
  chrome: 'CH',
  gmail: 'GM',
  teams: 'TM',
  whatsapp: 'WA',
  spotify: 'SP',
  news: 'NW',
};

function cardState(app: ApplicationRuntimeStatus): {
  label: string;
  tone: 'active' | 'minimized' | 'background' | 'ready' | 'missing' | 'failed';
} {
  if (app.status === 'FAILED' || app.error) {
    return { label: 'ACTION FAILED', tone: 'failed' };
  }
  if (app.running && app.windowFound) {
    if (app.focusSucceeded === false && app.result && /FOCUS|LIMITED/i.test(String(app.result))) {
      return { label: 'RUNNING — FOCUS LIMITED', tone: 'active' };
    }
    return { label: 'ACTIVE', tone: 'active' };
  }
  if (app.running && !app.windowFound) {
    return { label: 'BACKGROUND', tone: 'background' };
  }
  if (!app.resolved) {
    return { label: 'NOT CONFIGURED', tone: 'missing' };
  }
  return { label: 'READY TO LAUNCH', tone: 'ready' };
}

export function ApplicationsCommandGrid() {
  const { workspace } = useDashboard();
  const apps = workspace.applications;

  return (
    <div className={styles.root} data-testid="applications-panel">
      <header className={styles.header}>
        <div>
          <h2>Applications Command Centre</h2>
          <p>Open or focus approved workspace applications</p>
        </div>
        <button
          type="button"
          className={styles.refresh}
          data-no-swipe
          onClick={() => void workspace.refresh()}
          disabled={workspace.loading || workspace.pending}
        >
          Refresh
        </button>
      </header>

      {workspace.error && <p className={styles.error}>{workspace.error}</p>}

      <div className={styles.grid}>
        {apps.map((app) => {
          const state = cardState(app);
          const pending = workspace.pendingAppIds.has(app.applicationId);
          const initials = INITIALS[app.applicationId] ?? app.displayName.slice(0, 2).toUpperCase();
          return (
            <article
              key={app.applicationId}
              className={`${styles.card} ${styles[state.tone]}`}
              data-no-swipe
            >
              <div className={styles.icon} aria-hidden="true">
                {initials}
              </div>
              <div className={styles.body}>
                <h3>{app.displayName}</h3>
                <p className={styles.state}>{state.label}</p>
                <ul className={styles.meta}>
                  <li>{app.enabled ? 'Enabled' : 'Disabled'}</li>
                  <li>{app.running ? 'Running' : 'Stopped'}</li>
                  <li>{app.windowFound ? 'Window found' : 'No window'}</li>
                  <li>Last: {app.result ?? app.status}</li>
                </ul>
              </div>
              <div className={styles.actions}>
                <button
                  type="button"
                  disabled={pending || !app.enabled}
                  onClick={() => void workspace.openApp(app.applicationId)}
                >
                  {pending ? 'Working…' : 'Open'}
                </button>
                <button
                  type="button"
                  disabled={pending || !app.enabled}
                  onClick={() => void workspace.focusApp(app.applicationId)}
                >
                  Focus
                </button>
              </div>
            </article>
          );
        })}
      </div>

      {apps.length === 0 && !workspace.loading && (
        <p className={styles.empty}>No applications configured</p>
      )}
    </div>
  );
}
