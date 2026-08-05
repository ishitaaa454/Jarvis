import { useDashboard } from '../../context/DashboardContext';
import styles from './ActivationSequence.module.css';

export function ActivationSequence() {
  const {
    assistantState,
    connectionStatus,
    dataStale,
    voice,
    speech,
    workspace,
  } = useDashboard();

  const connected = connectionStatus === 'CONNECTED';
  let headline = 'SYSTEM ONLINE';
  let detail: string | null = null;
  let progress: string | null = null;

  if (!connected) {
    headline = connectionStatus === 'RECONNECTING' ? 'CONNECTION LOST' : 'BACKEND OFFLINE';
    detail = dataStale ? 'Showing last known status (STALE)' : 'Waiting for backend';
  } else if (voice.activationVisible || assistantState === 'PROCESSING') {
    if (voice.activationVisible) {
      headline = 'VOICE ACTIVATION CONFIRMED';
    }
    if (assistantState === 'PROCESSING') {
      headline = 'PROCESSING AUTHORIZATION';
    }
  } else if (assistantState === 'SPEAKING' || speech.speaking) {
    headline = 'JARVIS SPEAKING';
    detail = speech.currentUtterance?.text ?? null;
    if (speech.currentUtterance) {
      progress = `${speech.currentUtterance.index} / ${speech.currentUtterance.total}`;
    }
  } else if (assistantState === 'INITIALIZING_WORKSPACE') {
    headline = 'INITIALIZING WORKSPACE';
  } else if (assistantState === 'OPENING_APPLICATIONS' || workspace.isRunning) {
    headline = 'OPENING WORKSPACE';
    const current = workspace.workspaceStatus?.current_application;
    const app = workspace.applications.find(
      (item) => item.applicationId === current || item.displayName === current,
    );
    detail = app?.displayName ?? current ?? 'Preparing applications';
    const p = workspace.workspaceStatus?.progress;
    if (p && p.total > 0) {
      progress = `${p.completed} / ${p.total}`;
    }
  } else if (assistantState === 'READY') {
    headline = 'ALL SYSTEMS OPERATIONAL';
  } else if (assistantState === 'ERROR') {
    headline = 'SYSTEM ERROR';
    detail =
      voice.error ||
      speech.error ||
      workspace.error ||
      workspace.workspaceStatus?.last_error ||
      null;
  } else if (assistantState === 'LISTENING') {
    headline = 'AWAITING COMMAND';
    detail = 'SYSTEM ONLINE';
  } else if (assistantState === 'IDLE') {
    headline = 'SYSTEM ONLINE';
  }

  return (
    <div className={styles.wrap} data-testid="activation-sequence">
      <p className={styles.headline}>{headline}</p>
      {detail && <p className={styles.detail}>{detail}</p>}
      {progress && <p className={styles.progress}>{progress}</p>}
    </div>
  );
}
