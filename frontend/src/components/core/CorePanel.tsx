import { Link } from 'react-router-dom';

import { useDashboard } from '../../context/DashboardContext';
import { formatPercent, formatRate } from '../../utils/formatMetrics';
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
    systemMonitor,
    commandCentre,
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
  const snap = systemMonitor.snapshot;

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
            value={snap?.cpu.usage_percent ?? health?.system.cpu_percent ?? null}
            history={cpuHistory}
          />
          <CircularMetric
            label="Memory"
            value={snap?.memory.usage_percent ?? health?.system.memory_percent ?? null}
            history={memHistory}
          />
          <div className={styles.compactSystem}>
            <h3>Current focus</h3>
            <p>
              {commandCentre.inventory?.foreground_application_id
                ? commandCentre.inventory.applications.find(
                    (app) =>
                      app.application_id ===
                      commandCentre.inventory?.foreground_application_id,
                  )?.display_name ?? 'Approved app'
                : 'No approved app focused'}
            </p>
            <p className={styles.focusMeta}>
              {commandCentre.inventory?.running_applications ?? 0} Jarvis apps open
            </p>
            <p className={styles.focusMeta}>
              Return:{' '}
              {commandCentre.hotkey?.shortcuts[0]?.display ?? 'Ctrl + Alt + J'}
            </p>
            <Link to="/system?section=network">
              RX {formatRate(snap?.network.receive_bytes_per_second)}
            </Link>
            <Link to="/system?section=network">
              TX {formatRate(snap?.network.send_bytes_per_second)}
            </Link>
            <Link to="/system?section=power">
              Battery{' '}
              {snap?.battery.present
                ? formatPercent(snap.battery.percent)
                : 'NONE'}
            </Link>
            <Link to="/system?section=gpu">
              GPU{' '}
              {snap?.gpu.availability === 'AVAILABLE'
                ? formatPercent(snap.gpu.devices[0]?.usage_percent)
                : 'N/A'}
            </Link>
          </div>
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
                <span>Monitor</span>
                <strong>{systemMonitor.status?.status ?? 'UNKNOWN'}</strong>
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
