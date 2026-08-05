import { describeWorkspaceStatus, type WorkspaceBanner } from '../../hooks/useWorkspaceStatus';
import type { ApplicationRuntimeStatus, WorkspaceStatus } from '../../types/workspace';
import { ApplicationLaunchRow } from './ApplicationLaunchRow';
import styles from './WorkspaceStatusPanel.module.css';

interface WorkspaceStatusPanelProps {
  workspaceStatus: WorkspaceStatus | null;
  applications: ApplicationRuntimeStatus[];
  loading: boolean;
  error: string | null;
  pending: boolean;
  pendingAppIds: Set<string>;
  banner: WorkspaceBanner;
  isRunning: boolean;
  onStart: () => void;
  onCancel: () => void;
  onRefresh: () => void;
  onOpenApp: (appId: string) => void;
  onFocusApp: (appId: string) => void;
}

const BANNER_TEXT: Record<Exclude<WorkspaceBanner, null>, string> = {
  OPENING: 'OPENING WORKSPACE',
  READY: 'WORKSPACE READY',
  PARTIAL: 'PARTIALLY READY',
};

export function WorkspaceStatusPanel({
  workspaceStatus,
  applications,
  loading,
  error,
  pending,
  pendingAppIds,
  banner,
  isRunning,
  onStart,
  onCancel,
  onRefresh,
  onOpenApp,
  onFocusApp,
}: WorkspaceStatusPanelProps) {
  const progress = workspaceStatus?.progress ?? { completed: 0, total: 0 };
  const progressPercent =
    progress.total > 0 ? Math.round((progress.completed / progress.total) * 100) : 0;

  const canStart = !pending && !isRunning && workspaceStatus?.enabled !== false;
  const canCancel = !pending && isRunning;
  const currentAppName = workspaceStatus?.current_application
    ? applications.find((app) => app.applicationId === workspaceStatus.current_application)
        ?.displayName ?? workspaceStatus.current_application
    : null;

  return (
    <section className={`glass-panel ${styles.panel}`} aria-labelledby="workspace-status-heading">
      <header className={styles.header}>
        <h2 id="workspace-status-heading">Workspace</h2>
        <p className="muted">Launches your configured applications in one sequence</p>
      </header>

      <div
        className={`${styles.banner} ${banner ? styles.bannerVisible : ''} ${
          banner === 'READY'
            ? styles.bannerReady
            : banner === 'PARTIAL'
              ? styles.bannerPartial
              : ''
        }`}
        role="status"
        aria-live="assertive"
        aria-hidden={!banner}
      >
        {banner ? BANNER_TEXT[banner] : ''}
      </div>

      <div className={styles.live} aria-live="polite" aria-atomic="true">
        {loading ? (
          <p className="muted">Loading workspace status…</p>
        ) : (
          <>
            <dl className={styles.meta}>
              <div>
                <dt>Status</dt>
                <dd>{describeWorkspaceStatus(workspaceStatus?.status)}</dd>
              </div>
              <div>
                <dt>Profile</dt>
                <dd>{workspaceStatus?.profile ?? 'default'}</dd>
              </div>
              <div>
                <dt>Enabled apps</dt>
                <dd>{workspaceStatus?.total_enabled ?? 0}</dd>
              </div>
              <div>
                <dt>Current</dt>
                <dd>{currentAppName ?? '—'}</dd>
              </div>
            </dl>

            <div
              className={styles.progressBar}
              role="progressbar"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={progressPercent}
              aria-label="Workspace launch progress"
            >
              <div className={styles.progressFill} style={{ width: `${progressPercent}%` }} />
            </div>
            <p className={styles.progressLabel}>
              {progress.completed} / {progress.total} applications
            </p>
          </>
        )}
      </div>

      {error ? (
        <p className={styles.error} role="alert">
          {error}
        </p>
      ) : null}

      <div className={styles.actions}>
        <button
          type="button"
          className={styles.button}
          onClick={onStart}
          disabled={!canStart}
          aria-label="Start workspace"
        >
          {isRunning ? 'Running…' : 'Start workspace'}
        </button>
        <button
          type="button"
          className={styles.buttonSecondary}
          onClick={onCancel}
          disabled={!canCancel}
          aria-label="Cancel workspace launch"
        >
          Cancel
        </button>
        <button
          type="button"
          className={styles.buttonSecondary}
          onClick={onRefresh}
          disabled={pending || isRunning}
          aria-label="Refresh workspace application registry"
        >
          Refresh
        </button>
      </div>

      {applications.length > 0 ? (
        <ul className={styles.appList}>
          {applications.map((app) => (
            <ApplicationLaunchRow
              key={app.applicationId}
              app={app}
              pending={pendingAppIds.has(app.applicationId)}
              onOpen={onOpenApp}
              onFocus={onFocusApp}
            />
          ))}
        </ul>
      ) : !loading ? (
        <p className="muted">No workspace applications configured.</p>
      ) : null}
    </section>
  );
}
