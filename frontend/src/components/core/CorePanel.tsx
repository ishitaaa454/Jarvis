import { useDashboard } from '../../context/DashboardContext';
import { CircularMetric } from '../metrics/CircularMetric';
import { ActivityTimeline } from '../timeline/ActivityTimeline';
import { ActivationSequence } from './ActivationSequence';
import { JarvisCore } from './JarvisCore';
import styles from './CorePanel.module.css';

export function CorePanel() {
  const {
    assistantState,
    connectionStatus,
    health,
    metricHistory,
    voice,
    speech,
    workspace,
    reducedMotion,
    tabVisible,
    dataStale,
  } = useDashboard();

  const connected = connectionStatus === 'CONNECTED';
  const progress =
    workspace.workspaceStatus && workspace.workspaceStatus.progress.total > 0
      ? workspace.workspaceStatus.progress.completed /
        workspace.workspaceStatus.progress.total
      : speech.currentUtterance
        ? speech.currentUtterance.index / Math.max(1, speech.currentUtterance.total)
        : null;

  const coreLabel =
    assistantState === 'LISTENING'
      ? 'Listening'
      : assistantState === 'SPEAKING'
        ? 'Speaking'
        : assistantState === 'READY'
          ? 'Ready'
          : assistantState === 'OPENING_APPLICATIONS'
            ? 'Opening'
            : assistantState?.replaceAll('_', ' ') ?? 'Offline';

  const cpuHistory = metricHistory.samples.map((s) => s.cpuPercent);
  const memHistory = metricHistory.samples.map((s) => s.memoryPercent);

  return (
    <div className={styles.root} data-testid="core-panel">
      <div className={styles.hero}>
        <JarvisCore
          assistantState={assistantState}
          connected={connected}
          reducedMotion={reducedMotion}
          tabVisible={tabVisible}
          progressRatio={progress}
          label={coreLabel}
        />
        <ActivationSequence />
        {dataStale && <p className={styles.stale}>LIVE DATA STALE</p>}
      </div>

      <div className={styles.sideGrid}>
        <div className={styles.metrics}>
          <CircularMetric
            label="CPU"
            value={health?.system.cpu_percent ?? null}
            history={cpuHistory}
          />
          <CircularMetric
            label="Memory"
            value={health?.system.memory_percent ?? null}
            history={memHistory}
          />
          <div className={styles.services}>
            <h3>Runtime</h3>
            <ul>
              <li>
                <span>Wake</span>
                <strong>{voice.voiceStatus?.status ?? 'UNKNOWN'}</strong>
              </li>
              <li>
                <span>Piper</span>
                <strong>{speech.ttsStatus?.status ?? 'UNKNOWN'}</strong>
              </li>
              <li>
                <span>Workspace</span>
                <strong>{workspace.workspaceStatus?.status ?? 'UNKNOWN'}</strong>
              </li>
              <li>
                <span>Assistant</span>
                <strong>{assistantState ?? 'UNKNOWN'}</strong>
              </li>
            </ul>
          </div>
        </div>
        <ActivityTimeline />
      </div>

      <p className={styles.hint}>
        Swipe, drag, or use ← → keys · Home returns to Core · Esc exits fullscreen
      </p>
    </div>
  );
}
