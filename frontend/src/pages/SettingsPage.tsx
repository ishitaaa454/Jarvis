import { useEffect, useState } from 'react';

import { describeTtsStatus } from '../hooks/useSpeechStatus';
import { describeVoiceStatus } from '../hooks/useVoiceStatus';
import { fetchTtsDevices } from '../services/ttsApi';
import { fetchVoiceDevices } from '../services/voiceApi';
import type { OutputDeviceInfo, TtsStatus } from '../types/speech';
import type { AudioDevice, VoiceStatus } from '../types/voice';
import styles from './SettingsPage.module.css';

const LATER_SECTIONS = [
  {
    title: 'Workspace applications',
    description: 'Default app launch order for workspace initialization.',
  },
  {
    title: 'Dashboard appearance',
    description: 'Theme density, accent intensity, and layout preferences.',
  },
  {
    title: 'Integrations',
    description: 'Calendar, email, news, and local AI connectors.',
  },
];

const WELCOME_LINES = [
  'Welcome back, Ishita. Initializing your workspace.',
  'All systems are online.',
  'Opening your workspace now.',
];

interface SettingsPageProps {
  voiceStatus: VoiceStatus | null;
  voiceLoading: boolean;
  voiceError: string | null;
  voicePending: boolean;
  onStart: () => void;
  onStop: () => void;
  onSelectDevice: (deviceId: number) => void;
  onRetry: () => void;
  ttsStatus: TtsStatus | null;
  ttsLoading: boolean;
  ttsError: string | null;
  ttsPending: boolean;
  onSelectOutputDevice: (deviceId: number) => void;
  onTestWelcome: () => void;
  onCancelSpeech: () => void;
  onRetryTts: () => void;
}

export function SettingsPage({
  voiceStatus,
  voiceLoading,
  voiceError,
  voicePending,
  onStart,
  onStop,
  onSelectDevice,
  onRetry,
  ttsStatus,
  ttsLoading,
  ttsError,
  ttsPending,
  onSelectOutputDevice,
  onTestWelcome,
  onCancelSpeech,
  onRetryTts,
}: SettingsPageProps) {
  const [devices, setDevices] = useState<AudioDevice[]>([]);
  const [devicesError, setDevicesError] = useState<string | null>(null);
  const [devicesLoading, setDevicesLoading] = useState(true);
  const [outputs, setOutputs] = useState<OutputDeviceInfo[]>([]);
  const [outputsError, setOutputsError] = useState<string | null>(null);
  const [outputsLoading, setOutputsLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const list = await fetchVoiceDevices();
        if (!cancelled) {
          setDevices(list);
          setDevicesError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setDevicesError(
            err instanceof Error ? err.message : 'Unable to list microphones',
          );
        }
      } finally {
        if (!cancelled) setDevicesLoading(false);
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const list = await fetchTtsDevices();
        if (!cancelled) {
          setOutputs(list);
          setOutputsError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setOutputsError(
            err instanceof Error ? err.message : 'Unable to list output devices',
          );
        }
      } finally {
        if (!cancelled) setOutputsLoading(false);
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  const status = voiceStatus?.status;
  const showRetry =
    status === 'ERROR' || status === 'MODEL_MISSING' || Boolean(voiceError);
  const canStart =
    !voicePending &&
    status !== 'LISTENING' &&
    status !== 'STARTING' &&
    status !== 'DISABLED';
  const canStop =
    !voicePending && (status === 'LISTENING' || status === 'ACTIVATION_DETECTED');

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
    Boolean(ttsError);

  return (
    <div className={styles.page}>
      <header>
        <h1 className="page-title">SETTINGS</h1>
        <p className="page-subtitle">Voice listener and speech output</p>
      </header>

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
              disabled={voicePending || devicesLoading || devices.length === 0}
              value={voiceStatus?.microphone?.id ?? ''}
              onChange={(event) => {
                const value = event.target.value;
                if (value === '') return;
                onSelectDevice(Number(value));
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
        {voiceError ? (
          <p className={styles.error} role="alert">
            {voiceError}
          </p>
        ) : null}

        <div className={styles.actions}>
          <button type="button" className={styles.actionBtn} onClick={onStart} disabled={!canStart} aria-label="Start wake listener">
            Start
          </button>
          <button type="button" className={styles.actionBtnSecondary} onClick={onStop} disabled={!canStop} aria-label="Stop wake listener">
            Stop
          </button>
          {showRetry ? (
            <button type="button" className={styles.actionBtnSecondary} onClick={onRetry} disabled={voicePending} aria-label="Retry starting wake listener">
              Retry
            </button>
          ) : null}
        </div>
      </section>

      <section className={`glass-panel ${styles.card}`} aria-labelledby="speech-settings-heading">
        <h2 id="speech-settings-heading">Speech output</h2>
        <p className="muted">
          Offline Piper TTS with British male voice <code>en_GB-alan-medium</code>.
          Welcome lines are fixed in this phase.
        </p>

        <div className={styles.voiceGrid} aria-live="polite">
          <div className={styles.stat}>
            <span>TTS enabled</span>
            <strong>{ttsStatus?.enabled ? 'Yes' : 'No'}</strong>
          </div>
          <div className={styles.stat}>
            <span>Piper status</span>
            <strong>{describeTtsStatus(ttsStatus?.status)}</strong>
          </div>
          <div className={styles.stat}>
            <span>Voice</span>
            <strong>{ttsStatus?.voice ?? 'en_GB-alan-medium'}</strong>
          </div>
          <div className={styles.stat}>
            <span>Model</span>
            <strong>{ttsStatus?.model_loaded ? 'Loaded' : 'Missing'}</strong>
          </div>
          <div className={styles.stat}>
            <span>Volume</span>
            <strong>{ttsStatus?.volume ?? '—'}</strong>
          </div>
          <div className={styles.stat}>
            <span>Length scale</span>
            <strong>{ttsStatus?.length_scale ?? '—'}</strong>
          </div>
          <div className={styles.stat}>
            <span>Sentence pause</span>
            <strong>
              {ttsStatus?.sentence_pause_ms != null
                ? `${ttsStatus.sentence_pause_ms} ms`
                : '—'}
            </strong>
          </div>

          <label className={styles.field}>
            Output device
            <select
              aria-label="Select audio output device"
              disabled={ttsPending || outputsLoading || outputs.length === 0}
              value={ttsStatus?.output_device?.id ?? ''}
              onChange={(event) => {
                const value = event.target.value;
                if (value === '') return;
                onSelectOutputDevice(Number(value));
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
        {ttsError ? (
          <p className={styles.error} role="alert">
            {ttsError}
          </p>
        ) : null}
        {ttsLoading || voiceLoading ? <p className="muted">Loading…</p> : null}

        <div className={styles.actions}>
          <button
            type="button"
            className={styles.actionBtn}
            onClick={onTestWelcome}
            disabled={ttsPending || speaking || !ttsReady}
            aria-label="Test welcome sequence"
          >
            Test welcome
          </button>
          <button
            type="button"
            className={styles.actionBtnSecondary}
            onClick={onCancelSpeech}
            disabled={ttsPending || !speaking}
            aria-label="Cancel speech"
          >
            Cancel
          </button>
          {showTtsRetry ? (
            <button
              type="button"
              className={styles.actionBtnSecondary}
              onClick={onRetryTts}
              disabled={ttsPending}
              aria-label="Retry speech engine"
            >
              Retry
            </button>
          ) : null}
        </div>
      </section>

      <div className={styles.list}>
        {LATER_SECTIONS.map((section) => (
          <section key={section.title} className={`glass-panel ${styles.card}`}>
            <h2>{section.title}</h2>
            <p className="muted">{section.description}</p>
            <p className="placeholder-note">Read-only placeholder — Available in a later phase</p>
            <fieldset disabled className={styles.fieldset}>
              <label>
                Value
                <input type="text" value="Not configured" readOnly />
              </label>
            </fieldset>
          </section>
        ))}
      </div>
    </div>
  );
}
