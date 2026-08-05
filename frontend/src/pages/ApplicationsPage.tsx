import { describeApplicationStatus } from '../hooks/useWorkspaceStatus';
import type { ApplicationRuntimeStatus } from '../types/workspace';
import styles from './ApplicationsPage.module.css';

interface ApplicationsPageProps {
  applications: ApplicationRuntimeStatus[];
  loading: boolean;
  error: string | null;
  pendingAppIds: Set<string>;
  onOpenApp: (appId: string) => void;
  onFocusApp: (appId: string) => void;
}

const LAUNCH_TYPE_LABEL: Record<string, string> = {
  executable: 'Executable',
  url: 'URL',
  uri: 'URI',
  start_app: 'Start app',
  browser_url: 'Browser URL',
};

function initialsFor(name: string): string {
  const words = name.trim().split(/\s+/).filter(Boolean);
  if (words.length === 0) return '??';
  if (words.length === 1) return words[0].slice(0, 2).toUpperCase();
  return `${words[0][0]}${words[1][0]}`.toUpperCase();
}

function statusTone(status: ApplicationRuntimeStatus['status']): string {
  switch (status) {
    case 'READY':
    case 'ALREADY_RUNNING':
      return styles.toneReady;
    case 'FAILED':
      return styles.toneFailed;
    case 'SKIPPED':
    case 'CANCELLED':
      return styles.toneSkipped;
    case 'PENDING':
      return styles.tonePending;
    default:
      return styles.toneActive;
  }
}

export function ApplicationsPage({
  applications,
  loading,
  error,
  pendingAppIds,
  onOpenApp,
  onFocusApp,
}: ApplicationsPageProps) {
  return (
    <div className={styles.page}>
      <header>
        <h1 className="page-title">APPLICATIONS</h1>
        <p className="page-subtitle">Workspace targets</p>
      </header>

      {error ? (
        <p className={styles.pageError} role="alert">
          {error}
        </p>
      ) : null}

      {loading ? (
        <p className="muted">Loading applications…</p>
      ) : applications.length === 0 ? (
        <p className="muted">No workspace applications configured.</p>
      ) : (
        <div className={styles.grid}>
          {applications.map((app) => {
            const pending = pendingAppIds.has(app.applicationId);
            const canFocus = app.running && !pending;
            return (
              <article key={app.applicationId} className={`glass-panel ${styles.tile}`}>
                <div className={styles.icon} aria-hidden="true">
                  {initialsFor(app.displayName)}
                </div>
                <h2 className={styles.name}>{app.displayName}</h2>
                <p className={styles.meta}>
                  {LAUNCH_TYPE_LABEL[app.launchType] ?? app.launchType}
                  {app.enabled ? '' : ' \u00B7 Disabled'}
                </p>
                <p
                  className={`${styles.status} ${statusTone(app.status)}`}
                  aria-live="polite"
                >
                  {describeApplicationStatus(app.status)}
                </p>
                <div className={styles.flags}>
                  <span>{app.running ? 'Running' : 'Not running'}</span>
                  <span>{app.windowFound ? 'Window found' : 'No window'}</span>
                </div>
                {app.error ? (
                  <p className={styles.error} role="alert">
                    {app.error}
                  </p>
                ) : null}
                <div className={styles.actions}>
                  <button
                    type="button"
                    className={styles.button}
                    onClick={() => onOpenApp(app.applicationId)}
                    disabled={pending}
                    aria-label={`Open ${app.displayName}`}
                  >
                    {pending ? 'Working…' : 'Open'}
                  </button>
                  <button
                    type="button"
                    className={styles.buttonSecondary}
                    onClick={() => onFocusApp(app.applicationId)}
                    disabled={!canFocus}
                    aria-label={`Focus ${app.displayName}`}
                  >
                    Focus
                  </button>
                </div>
              </article>
            );
          })}
        </div>
      )}
    </div>
  );
}
