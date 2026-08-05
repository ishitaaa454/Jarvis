import { describeApplicationStatus } from '../../hooks/useWorkspaceStatus';
import type { ApplicationRuntimeStatus } from '../../types/workspace';
import styles from './ApplicationLaunchRow.module.css';

interface ApplicationLaunchRowProps {
  app: ApplicationRuntimeStatus;
  pending: boolean;
  onOpen: (appId: string) => void;
  onFocus: (appId: string) => void;
}

const LAUNCH_TYPE_LABEL: Record<string, string> = {
  executable: 'Executable',
  url: 'URL',
  uri: 'URI',
  start_app: 'Start app',
  browser_url: 'Browser URL',
};

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

export function ApplicationLaunchRow({
  app,
  pending,
  onOpen,
  onFocus,
}: ApplicationLaunchRowProps) {
  const canFocus = app.running && !pending;

  return (
    <li className={styles.row}>
      <div className={styles.info}>
        <span className={styles.name}>{app.displayName}</span>
        <span className={styles.meta}>
          {LAUNCH_TYPE_LABEL[app.launchType] ?? app.launchType}
          {app.enabled ? '' : ' \u00B7 Disabled'}
        </span>
      </div>

      <div className={styles.stateGroup} aria-live="polite" aria-atomic="true">
        <span className={`${styles.statusChip} ${statusTone(app.status)}`}>
          {describeApplicationStatus(app.status)}
        </span>
        <span className={styles.flag}>{app.running ? 'Running' : 'Not running'}</span>
        <span className={styles.flag}>{app.windowFound ? 'Window found' : 'No window'}</span>
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
          onClick={() => onOpen(app.applicationId)}
          disabled={pending}
          aria-label={`Open ${app.displayName}`}
        >
          {pending ? 'Working…' : 'Open'}
        </button>
        <button
          type="button"
          className={styles.buttonSecondary}
          onClick={() => onFocus(app.applicationId)}
          disabled={!canFocus}
          aria-label={`Focus ${app.displayName}`}
        >
          Focus
        </button>
      </div>
    </li>
  );
}
