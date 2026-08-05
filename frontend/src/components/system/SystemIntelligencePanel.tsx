import { useDashboard } from '../../context/DashboardContext';
import { CircularMetric } from '../metrics/CircularMetric';
import styles from './SystemIntelligencePanel.module.css';

export function SystemIntelligencePanel() {
  const {
    health,
    metricHistory,
    assistantState,
    connectionStatus,
    connectedAt,
    dataStale,
    voice,
    speech,
    workspace,
  } = useDashboard();

  const cpuHistory = metricHistory.samples.map((s) => s.cpuPercent);
  const memHistory = metricHistory.samples.map((s) => s.memoryPercent);

  return (
    <div className={styles.root} data-testid="system-panel">
      <header className={styles.header}>
        <h2>System Intelligence</h2>
        <p>Live host and runtime status from the local backend</p>
      </header>

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
      </div>

      <section className={styles.tableSection}>
        <h3>Core metrics</h3>
        <table>
          <tbody>
            <tr>
              <th scope="row">Platform</th>
              <td>{health?.system.platform ?? 'UNKNOWN'}</td>
            </tr>
            <tr>
              <th scope="row">Backend version</th>
              <td>{health?.version ?? 'UNKNOWN'}</td>
            </tr>
            <tr>
              <th scope="row">Assistant state</th>
              <td>{assistantState ?? 'UNKNOWN'}</td>
            </tr>
            <tr>
              <th scope="row">Health</th>
              <td>{health?.status ?? 'UNKNOWN'}</td>
            </tr>
          </tbody>
        </table>
      </section>

      <section className={styles.tableSection}>
        <h3>Runtime services</h3>
        <table>
          <tbody>
            <tr>
              <th scope="row">Backend</th>
              <td>
                {connectionStatus}
                {dataStale ? ' (STALE)' : ''}
              </td>
            </tr>
            <tr>
              <th scope="row">WebSocket</th>
              <td>{connectionStatus}</td>
            </tr>
            <tr>
              <th scope="row">Microphone</th>
              <td>{voice.voiceStatus?.microphone?.name ?? 'UNKNOWN'}</td>
            </tr>
            <tr>
              <th scope="row">Vosk wake listener</th>
              <td>{voice.voiceStatus?.status ?? 'UNKNOWN'}</td>
            </tr>
            <tr>
              <th scope="row">Piper</th>
              <td>{speech.ttsStatus?.status ?? 'UNKNOWN'}</td>
            </tr>
            <tr>
              <th scope="row">Output device</th>
              <td>{speech.ttsStatus?.output_device?.name ?? 'UNKNOWN'}</td>
            </tr>
            <tr>
              <th scope="row">Workspace controller</th>
              <td>{workspace.workspaceStatus?.status ?? 'UNKNOWN'}</td>
            </tr>
            <tr>
              <th scope="row">Application registry</th>
              <td>
                {workspace.workspaceStatus
                  ? `${workspace.workspaceStatus.total_enabled}/${workspace.workspaceStatus.total_configured} enabled`
                  : 'UNKNOWN'}
              </td>
            </tr>
            <tr>
              <th scope="row">Process discovery</th>
              <td>Available</td>
            </tr>
            <tr>
              <th scope="row">Window control</th>
              <td>Available / Limited by Windows focus policy</td>
            </tr>
          </tbody>
        </table>
      </section>

      <section className={styles.tableSection}>
        <h3>Session</h3>
        <table>
          <tbody>
            <tr>
              <th scope="row">Dashboard connected</th>
              <td>
                {connectedAt
                  ? new Intl.DateTimeFormat(undefined, {
                      hour: 'numeric',
                      minute: '2-digit',
                      second: '2-digit',
                    }).format(new Date(connectedAt))
                  : 'UNKNOWN'}
              </td>
            </tr>
            <tr>
              <th scope="row">Last wake</th>
              <td>{voice.voiceStatus?.last_activation_at ?? 'None'}</td>
            </tr>
            <tr>
              <th scope="row">Last spoken</th>
              <td>{speech.ttsStatus?.last_spoken_at ?? 'None'}</td>
            </tr>
            <tr>
              <th scope="row">Last workspace run</th>
              <td>{workspace.workspaceStatus?.last_run?.finished_at ?? 'None'}</td>
            </tr>
            <tr>
              <th scope="row">Last workspace result</th>
              <td>{workspace.workspaceStatus?.last_run?.status ?? 'None'}</td>
            </tr>
          </tbody>
        </table>
      </section>

      <section className={styles.future}>
        <h3>Later phases</h3>
        <div className={styles.futureGrid}>
          {['GPU', 'Disk performance', 'Network throughput', 'Battery analytics', 'Device temperatures', 'Running-process table'].map(
            (label) => (
              <div key={label} className={styles.futureCard}>
                <strong>{label}</strong>
                <span>AVAILABLE IN A LATER PHASE</span>
              </div>
            ),
          )}
        </div>
      </section>
    </div>
  );
}
