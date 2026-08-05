import { useEffect, useState } from 'react';

import { useDashboard } from '../context/DashboardContext';
import { describeApplicationStatus } from '../hooks/useWorkspaceStatus';
import { describeTtsStatus } from '../hooks/useSpeechStatus';
import { describeVoiceStatus } from '../hooks/useVoiceStatus';
import { fetchTtsDevices } from '../services/ttsApi';
import { fetchVoiceDevices } from '../services/voiceApi';
import type { OutputDeviceInfo } from '../types/speech';
import type { AudioDevice } from '../types/voice';
import styles from './SettingsPage.module.css';

const LATER_SECTIONS = [
  {
    title: 'Integrations',
    description: 'Calendar, email, news, and local AI connectors.',
  },
];

const LAUNCH_TYPE_LABEL: Record<string, string> = {
  executable: 'Executable',
  url: 'URL',
  uri: 'URI',
  start_app: 'Start app',
  browser_url: 'Browser URL',
};

const WELCOME_LINES = [
  'Welcome back, Ishita. Initializing your workspace.',
  'All systems are online.',
  'Opening your workspace now.',
];

export function SettingsPage() {
  const {
    voice,
    speech,
    workspace,
    reducedMotionOverride,
    setReducedMotionOverride,
    reducedMotion,
  } = useDashboard();

  const voiceStatus = voice.voiceStatus;
  const ttsStatus = speech.ttsStatus;

  const [devices, setDevices] = useState<AudioDevice[]>([]);
  const [devicesError, setDevicesError] = useState<string | null>(null);
  const [devicesLoading, setDevicesLoading] = useState(true);
  const [outputs, setOutputs] = useState<OutputDeviceInfo[]>([]);
  const [outputsError, setOutputsError] = useState<string | null>(null);
  const [outputsLoading, setOutputsLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    void fetchVoiceDevices()
      .then((list) => {
        if (!cancelled) {
          setDevices(list);
          setDevicesError(null);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setDevicesError(err instanceof Error ? err.message : 'Unable to list microphones');
        }
      })
      .finally(() => {
        if (!cancelled) setDevicesLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    void fetchTtsDevices()
      .then((list) => {
        if (!cancelled) {
          setOutputs(list);
          setOutputsError(null);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setOutputsError(
            err instanceof Error ? err.message : 'Unable to list output devices',
          );
        }
      })
      .finally(() => {
        if (!cancelled) setOutputsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const status = voiceStatus?.status;
  const showRetry =
    status === 'ERROR' || status === 'MODEL_MISSING' || Boolean(voice.error);
  const canStart =
    !voice.pending &&
    status !== 'LISTENING' &&
    status !== 'STARTING' &&
    status !== 'DISABLED';
  const canStop =
    !voice.pending && (status === 'LISTENING' || status === 'ACTIVATION_DETECTED');

  const ttsReady = ttsStatus?.status === 'READY';
  const speaking =
    ttsStatus?.is_speaking ||
    ttsStatus?.status === 'SPEAKING' ||
    ttsStatus?.status === 'SYNTHESIZING';
  const showTtsRetry =
    ttsStatus?.status === 'ERROR' ||
    ttsStatus?.status === 'MODEL_MISSING' ||
    ttsStatus?.status === 'ENGINE_MISSING' ||
    ttsStatus?.status === 'OUTPUT_UNAVAILABLE' ||
    Boolean(speech.error);

  return (
    <div className={styles.page}>
      <header>
        <h1 className="page-title">SETTINGS</h1>
        <p className="page-subtitle">Voice, speech, workspace, and motion preferences</p>
      </header>

      <section className={`glass-panel ${styles.card}`} aria-labelledby="motion-settings-heading">
        <h2 id="motion-settings-heading">Motion</h2>
        <p className="muted">
          Respects your system reduced-motion preference. Optional override below.
        </p>
        <label className={styles.field}>
          Reduced motion
          <select
            aria-label="Reduced motion preference"
            value={
              reducedMotionOverride === null
                ? 'system'
                : reducedMotionOverride
                  ? 'on'
                  : 'off'
            }
            onChange={(event) => {
              const value = event.target.value;
              if (value === 'system') setReducedMotionOverride(null);
              else setReducedMotionOverride(value === 'on');
            }}
          >
            <option value="system">Follow system ({reducedMotion ? 'reduce' : 'full'})</option>
            <option value="on">Always reduce</option>
            <option value="off">Prefer full motion</option>
          </select>
        </label>
        <p className="muted">
          Browser fullscreen requires a user click. The dashboard cannot enter fullscreen
          automatically after wake-phrase detection.
        </p>
      </section>

      <section className={`glass-panel ${styles.card}`} aria-labelledby="wake-settings-heading">
        <h2 id="wake-settings-heading">Wake phrase</h2>
        <p className="muted">
          Offline detection of the fixed phrase below. Custom wake phrases will be
          considered in a later phase.
        </p>

        <div className={styles.voiceGrid} aria-live="polite">
          <label className={styles.field}>
            Configured wake phrase
            <input
              type="text"
              value={voiceStatus?.wake_phrase ?? 'Wake up Jarvis'}
              readOnly
              aria-readonly="true"
            />
          </label>

          <label className={styles.field}>
            Microphone
            <select
              aria-label="Select microphone"
              disabled={voice.pending || devicesLoading || devices.length === 0}
              value={voiceStatus?.microphone?.id ?? ''}
              onChange={(event) => {
                const value = event.target.value;
                if (value === '') return;
                void voice.selectDevice(Number(value));
              }}
            >
              <option value="">
                {devicesLoading ? 'Loading devices…' : 'Select a microphone'}
              </option>
              {devices.map((device) => (
                <option key={device.id} value={device.id}>
                  {device.name}
                  {device.is_default ? ' (default)' : ''}
                </option>
              ))}
            </select>
          </label>

          <div className={styles.stat}>
            <span>Listener</span>
            <strong>{describeVoiceStatus(status)}</strong>
          </div>
          <div className={styles.stat}>
            <span>Model</span>
            <strong>
              {voiceStatus?.status === 'MODEL_MISSING'
                ? 'Missing'
                : voiceStatus?.model_loaded
                  ? 'Loaded'
                  : 'Not loaded'}
            </strong>
          </div>
        </div>

        {devicesError ? (
          <p className={styles.error} role="alert">
            {devicesError}
          </p>
        ) : null}
        {voice.error ? (
          <p className={styles.error} role="alert">
            {voice.error}
          </p>
        ) : null}

        <div className={styles.actions}>
          <button
            type="button"
            className={styles.actionBtn}
            onClick={() => void voice.start()}
            disabled={!canStart}
            aria-label="Start wake listener"
          >
            Start
          </button>
          <button
            type="button"
            className={styles.actionBtnSecondary}
            onClick={() => void voice.stop()}
            disabled={!canStop}
            aria-label="Stop wake listener"
          >
            Stop
          </button>
          {showRetry ? (
            <button
              type="button"
              className={styles.actionBtnSecondary}
              onClick={() => void voice.start()}
              disabled={voice.pending}
              aria-label="Retry starting wake listener"
            >
              Retry
            </button>
          ) : null}
        </div>
      </section>

      <section className={`glass-panel ${styles.card}`} aria-labelledby="speech-settings-heading">
        <h2 id="speech-settings-heading">Speech output</h2>
        <p className="muted">
          Offline Piper TTS with British male voice <code>en_GB-alan-medium</code>.
        </p>

        <div className={styles.voiceGrid} aria-live="polite">
          <div className={styles.stat}>
            <span>Piper status</span>
            <strong>{describeTtsStatus(ttsStatus?.status)}</strong>
          </div>
          <div className={styles.stat}>
            <span>Voice</span>
            <strong>{ttsStatus?.voice ?? 'en_GB-alan-medium'}</strong>
          </div>
          <label className={styles.field}>
            Output device
            <select
              aria-label="Select audio output device"
              disabled={speech.pending || outputsLoading || outputs.length === 0}
              value={ttsStatus?.output_device?.id ?? ''}
              onChange={(event) => {
                const value = event.target.value;
                if (value === '') return;
                void speech.selectDevice(Number(value));
              }}
            >
              <option value="">
                {outputsLoading ? 'Loading devices…' : 'Select speakers'}
              </option>
              {outputs.map((device) => (
                <option key={device.id} value={device.id}>
                  {device.name}
                  {device.is_default ? ' (default)' : ''}
                </option>
              ))}
            </select>
          </label>
        </div>

        <div className={styles.welcomeLines}>
          <p className="muted">Configured welcome messages (read-only)</p>
          <ol>
            {WELCOME_LINES.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ol>
        </div>

        {outputsError ? (
          <p className={styles.error} role="alert">
            {outputsError}
          </p>
        ) : null}
        {speech.error ? (
          <p className={styles.error} role="alert">
            {speech.error}
          </p>
        ) : null}

        <div className={styles.actions}>
          <button
            type="button"
            className={styles.actionBtn}
            onClick={() => void speech.testWelcome()}
            disabled={speech.pending || speaking || !ttsReady}
            aria-label="Test welcome sequence"
          >
            Test welcome
          </button>
          <button
            type="button"
            className={styles.actionBtnSecondary}
            onClick={() => void speech.cancel()}
            disabled={speech.pending || !speaking}
            aria-label="Cancel speech"
          >
            Cancel
          </button>
          {showTtsRetry ? (
            <button
              type="button"
              className={styles.actionBtnSecondary}
              onClick={() => void speech.retry()}
              disabled={speech.pending}
              aria-label="Retry speech engine"
            >
              Retry
            </button>
          ) : null}
        </div>
      </section>

      <section className={`glass-panel ${styles.card}`} aria-labelledby="workspace-apps-heading">
        <h2 id="workspace-apps-heading">Workspace applications</h2>
        <p className="muted">
          Default launch order. Edit <code>backend/config/applications.json</code> for
          enable state and launch details. Arbitrary commands are not accepted.
        </p>

        {workspace.loading ? (
          <p className="muted">Loading applications…</p>
        ) : workspace.applications.length === 0 ? (
          <p className="muted">No workspace applications configured.</p>
        ) : (
          <div className={styles.tableWrap}>
            <table className={styles.appsTable} aria-live="polite">
              <thead>
                <tr>
                  <th scope="col">Order</th>
                  <th scope="col">Application</th>
                  <th scope="col">Launch type</th>
                  <th scope="col">Enabled</th>
                  <th scope="col">Running</th>
                  <th scope="col">Last status</th>
                </tr>
              </thead>
              <tbody>
                {workspace.applications.map((app) => (
                  <tr key={app.applicationId}>
                    <td>{app.order}</td>
                    <td>{app.displayName}</td>
                    <td>{LAUNCH_TYPE_LABEL[app.launchType] ?? app.launchType}</td>
                    <td>{app.enabled ? 'Yes' : 'No'}</td>
                    <td>{app.running ? 'Yes' : 'No'}</td>
                    <td>{describeApplicationStatus(app.status)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <div className={styles.list}>
        {LATER_SECTIONS.map((section) => (
          <section key={section.title} className={`glass-panel ${styles.card}`}>
            <h2>{section.title}</h2>
            <p className="muted">{section.description}</p>
            <p className="placeholder-note">Available in a later phase</p>
          </section>
        ))}
      </div>
    </div>
  );
}
