import { describeTtsStatus } from '../../hooks/useSpeechStatus';
import type { TtsStatus, UtteranceProgress } from '../../types/speech';
import styles from './WelcomeSequencePanel.module.css';

interface WelcomeSequencePanelProps {
  ttsStatus: TtsStatus | null;
  loading: boolean;
  error: string | null;
  pending: boolean;
  currentUtterance: UtteranceProgress | null;
  initializingVisible: boolean;
  sequenceCompleteVisible: boolean;
  speaking: boolean;
  onTestWelcome: () => void;
  onCancel: () => void;
  onRetry: () => void;
}

const WELCOME_LINES = [
  'Welcome back, Ishita. Initializing your workspace.',
  'All systems are online.',
  'Opening your workspace now.',
];

export function WelcomeSequencePanel({
  ttsStatus,
  loading,
  error,
  pending,
  currentUtterance,
  initializingVisible,
  sequenceCompleteVisible,
  speaking,
  onTestWelcome,
  onCancel,
  onRetry,
}: WelcomeSequencePanelProps) {
  const status = ttsStatus?.status;
  const showRetry =
    status === 'ERROR' ||
    status === 'MODEL_MISSING' ||
    status === 'ENGINE_MISSING' ||
    status === 'OUTPUT_UNAVAILABLE';
  const canTest = !pending && !speaking && status === 'READY';
  const canCancel = !pending && (speaking || initializingVisible);

  return (
    <section className={`glass-panel ${styles.panel}`} aria-labelledby="speech-engine-heading">
      <header className={styles.header}>
        <h2 id="speech-engine-heading">Speech Engine</h2>
        <p className="muted">Offline Piper — British male voice</p>
      </header>

      <div className={styles.live} aria-live="polite" aria-atomic="true">
        {loading ? (
          <p className="muted">Loading speech status…</p>
        ) : (
          <>
            <dl className={styles.meta}>
              <div>
                <dt>Engine</dt>
                <dd>{ttsStatus?.engine ?? 'Piper'}</dd>
              </div>
              <div>
                <dt>Voice</dt>
                <dd>British male ({ttsStatus?.voice ?? 'en_GB-alan-medium'})</dd>
              </div>
              <div>
                <dt>Status</dt>
                <dd>{describeTtsStatus(status)}</dd>
              </div>
              <div>
                <dt>Output</dt>
                <dd>{ttsStatus?.output_device?.name ?? 'Not selected'}</dd>
              </div>
              <div>
                <dt>Speaking</dt>
                <dd>{speaking ? 'Yes' : 'No'}</dd>
              </div>
              <div>
                <dt>Last spoken</dt>
                <dd>
                  {ttsStatus?.last_spoken_at
                    ? new Date(ttsStatus.last_spoken_at).toLocaleTimeString()
                    : 'None yet'}
                </dd>
              </div>
            </dl>

            {initializingVisible ? (
              <p className={styles.banner}>INITIALIZING VOICE RESPONSE</p>
            ) : null}
            {speaking && currentUtterance ? (
              <div className={styles.speakingBox}>
                <p className={styles.banner}>JARVIS SPEAKING</p>
                <p className={styles.progress}>
                  {currentUtterance.index} / {currentUtterance.total}
                </p>
                <p className={styles.sentence}>{currentUtterance.text}</p>
              </div>
            ) : null}
            {sequenceCompleteVisible ? (
              <p className={styles.bannerDone}>VOICE SEQUENCE COMPLETE</p>
            ) : null}

            <ol className={styles.lines}>
              {WELCOME_LINES.map((line, idx) => {
                const active = currentUtterance?.index === idx + 1;
                return (
                  <li key={line} className={active ? styles.activeLine : undefined}>
                    <span>{idx + 1}.</span> {line}
                  </li>
                );
              })}
            </ol>
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
          onClick={onTestWelcome}
          disabled={!canTest}
          aria-label="Test welcome sequence"
        >
          {pending && !speaking ? 'Starting…' : 'Test welcome'}
        </button>
        <button
          type="button"
          className={styles.buttonSecondary}
          onClick={onCancel}
          disabled={!canCancel}
          aria-label="Cancel speech"
        >
          Cancel speech
        </button>
        {showRetry ? (
          <button
            type="button"
            className={styles.buttonSecondary}
            onClick={onRetry}
            disabled={pending}
            aria-label="Retry speech engine"
          >
            Retry
          </button>
        ) : null}
      </div>
    </section>
  );
}
