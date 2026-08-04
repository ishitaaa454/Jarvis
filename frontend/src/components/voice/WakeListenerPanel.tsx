import { describeVoiceStatus } from '../../hooks/useVoiceStatus';
import type { VoiceStatus } from '../../types/voice';
import { MicrophoneStatus } from './MicrophoneStatus';
import styles from './WakeListenerPanel.module.css';

interface WakeListenerPanelProps {
  voiceStatus: VoiceStatus | null;
  loading: boolean;
  error: string | null;
  pending: boolean;
  onStart: () => void;
  onStop: () => void;
}

function modelLabel(status: VoiceStatus | null): string {
  if (!status) return 'Unknown';
  if (status.status === 'MODEL_MISSING') return 'Missing';
  if (status.model_loaded) return 'Loaded';
  if (status.status === 'LOADING_MODEL') return 'Loading…';
  return 'Not loaded';
}

function formatActivation(iso: string | null): string {
  if (!iso) return 'None yet';
  try {
    return new Date(iso).toLocaleTimeString();
  } catch {
    return iso;
  }
}

export function WakeListenerPanel({
  voiceStatus,
  loading,
  error,
  pending,
  onStart,
  onStop,
}: WakeListenerPanelProps) {
  const status = voiceStatus?.status;
  const canStart =
    !pending &&
    status !== 'LISTENING' &&
    status !== 'STARTING' &&
    status !== 'LOADING_MODEL' &&
    status !== 'DISABLED';
  const canStop =
    !pending && (status === 'LISTENING' || status === 'ACTIVATION_DETECTED');

  return (
    <section className={`glass-panel ${styles.panel}`} aria-labelledby="wake-listener-heading">
      <header className={styles.header}>
        <h2 id="wake-listener-heading">Wake Listener</h2>
        <p className="muted">Offline Vosk detection — local microphone only</p>
      </header>

      <div className={styles.live} aria-live="polite" aria-atomic="true">
        {loading ? (
          <p className="muted">Loading voice status…</p>
        ) : (
          <>
            <MicrophoneStatus voiceStatus={voiceStatus} />
            <dl className={styles.meta}>
              <div>
                <dt>Wake phrase</dt>
                <dd>{voiceStatus?.wake_phrase ?? 'Wake up, Jarvis'}</dd>
              </div>
              <div>
                <dt>Model</dt>
                <dd>{modelLabel(voiceStatus)}</dd>
              </div>
              <div>
                <dt>Last activation</dt>
                <dd>{formatActivation(voiceStatus?.last_activation_at ?? null)}</dd>
              </div>
              <div>
                <dt>Listener</dt>
                <dd>{describeVoiceStatus(status)}</dd>
              </div>
            </dl>
          </>
        )}
      </div>

      {error ? (
        <p className={styles.error} role="alert">
          {error}
        </p>
      ) : null}

      {voiceStatus?.status === 'MODEL_MISSING' ? (
        <p className={styles.hint}>
          Install a small English Vosk model under <code>backend/models/</code> and set{' '}
          <code>VOSK_MODEL_PATH</code>. See <code>backend/models/README.md</code>.
        </p>
      ) : null}

      <div className={styles.actions}>
        <button
          type="button"
          className={styles.button}
          onClick={onStart}
          disabled={!canStart}
          aria-label="Start wake listener"
        >
          {pending && canStart ? 'Starting…' : 'Start listener'}
        </button>
        <button
          type="button"
          className={styles.buttonSecondary}
          onClick={onStop}
          disabled={!canStop}
          aria-label="Stop wake listener"
        >
          {pending && canStop ? 'Stopping…' : 'Stop listener'}
        </button>
      </div>
    </section>
  );
}
