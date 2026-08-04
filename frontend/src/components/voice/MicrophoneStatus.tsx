import { describeVoiceStatus } from '../../hooks/useVoiceStatus';
import type { VoiceStatus } from '../../types/voice';
import styles from './MicrophoneStatus.module.css';

interface MicrophoneStatusProps {
  voiceStatus: VoiceStatus | null;
}

export function MicrophoneStatus({ voiceStatus }: MicrophoneStatusProps) {
  const micName = voiceStatus?.microphone?.name ?? 'Not selected';
  const listening = voiceStatus?.status === 'LISTENING';
  const unavailable =
    voiceStatus?.status === 'ERROR' ||
    voiceStatus?.status === 'MODEL_MISSING' ||
    !voiceStatus?.microphone?.name;

  const micLabel = unavailable && !listening ? 'Unavailable' : listening || voiceStatus?.microphone?.name ? 'Active' : 'Idle';

  return (
    <div className={styles.wrap} role="group" aria-label="Microphone status">
      <div className={styles.row}>
        <span className={styles.key}>MICROPHONE</span>
        <span className={styles.value} data-tone={unavailable ? 'warn' : 'ok'}>
          {micLabel}
        </span>
      </div>
      <p className={styles.detail}>{micName}</p>
      <div className={styles.row}>
        <span className={styles.key}>WAKE LISTENER</span>
        <span className={styles.value}>
          {describeVoiceStatus(voiceStatus?.status).toUpperCase()}
        </span>
      </div>
    </div>
  );
}
