import { useDashboard } from '../../context/DashboardContext';
import { describeTtsStatus } from '../../hooks/useSpeechStatus';
import { describeVoiceStatus } from '../../hooks/useVoiceStatus';
import { describeWorkspaceStatus } from '../../hooks/useWorkspaceStatus';
import styles from './GlobalStatusStrip.module.css';

function cell(label: string, value: string, tone: 'ok' | 'warn' | 'err' | 'muted' = 'ok') {
  return (
    <div className={`${styles.cell} ${styles[tone]}`} key={label}>
      <span className={styles.label}>{label}</span>
      <span className={styles.value}>{value}</span>
    </div>
  );
}

export function GlobalStatusStrip() {
  const { connectionStatus, dataStale, voice, speech, workspace } = useDashboard();

  const backend =
    connectionStatus === 'CONNECTED'
      ? dataStale
        ? 'STALE'
        : 'CONNECTED'
      : connectionStatus === 'RECONNECTING'
        ? 'RECONNECTING'
        : connectionStatus === 'CONNECTING'
          ? 'CONNECTING'
          : 'DISCONNECTED';

  const mic =
    voice.voiceStatus?.status === 'LISTENING'
      ? 'ACTIVE'
      : voice.voiceStatus?.status === 'STOPPED'
        ? 'STOPPED'
        : voice.voiceStatus
          ? String(voice.voiceStatus.status)
          : 'UNKNOWN';

  const voiceLabel = voice.voiceStatus
    ? describeVoiceStatus(voice.voiceStatus.status)
    : 'UNKNOWN';
  const piper = speech.ttsStatus
    ? describeTtsStatus(speech.ttsStatus.status)
    : 'UNKNOWN';
  const workspaceLabel = workspace.workspaceStatus
    ? describeWorkspaceStatus(workspace.workspaceStatus.status)
    : 'UNKNOWN';

  const backendTone =
    backend === 'CONNECTED' ? 'ok' : backend === 'STALE' || backend === 'RECONNECTING' ? 'warn' : 'err';

  return (
    <div className={styles.strip} role="status" aria-label="Global system status">
      {cell('Backend', backend, backendTone)}
      {cell('Microphone', mic, mic === 'ACTIVE' ? 'ok' : 'muted')}
      {cell('Voice', voiceLabel.toUpperCase(), 'muted')}
      {cell('Piper', piper.toUpperCase(), 'muted')}
      {cell('Workspace', workspaceLabel.toUpperCase(), 'muted')}
      {cell('Processing', 'LOCAL', 'ok')}
    </div>
  );
}
