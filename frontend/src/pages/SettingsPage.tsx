import { useEffect, useState } from 'react';

import { describeVoiceStatus } from '../hooks/useVoiceStatus';
import { fetchVoiceDevices } from '../services/voiceApi';
import type { AudioDevice, VoiceStatus } from '../types/voice';
import styles from './SettingsPage.module.css';

const LATER_SECTIONS = [
  {
    title: 'Voice',
    description: 'British male TTS profile and speech rate. Available in a later phase.',
  },
  {
    title: 'Welcome message',
    description: 'Spoken greeting lines after wake. Not editable yet.',
  },
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

interface SettingsPageProps {
  voiceStatus: VoiceStatus | null;
  voiceLoading: boolean;
  voiceError: string | null;
  voicePending: boolean;
  onStart: () => void;
  onStop: () => void;
  onSelectDevice: (deviceId: number) => void;
  onRetry: () => void;
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
}: SettingsPageProps) {
  const [devices, setDevices] = useState<AudioDevice[]>([]);
  const [devicesError, setDevicesError] = useState<string | null>(null);
  const [devicesLoading, setDevicesLoading] = useState(true);

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

  return (
    <div className={styles.page}>
      <header>
        <h1 className="page-title">SETTINGS</h1>
        <p className="page-subtitle">Voice listener and future configuration</p>
      </header>

      <section className={`glass-panel ${styles.card}`} aria-labelledby="wake-settings-heading">
        <h2 id="wake-settings-heading">Wake phrase</h2>
        <p className="muted">
          Offline detection of the fixed phrase below. Custom wake phrases will be
          considered in a later phase because the recognizer grammar and tests are
          designed for “Wake up, Jarvis.”
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
          <div className={styles.stat}>
            <span>Enabled</span>
            <strong>{voiceStatus?.enabled ? 'Yes' : 'No'}</strong>
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
        {voiceLoading ? <p className="muted">Loading voice status…</p> : null}

        <div className={styles.actions}>
          <button
            type="button"
            className={styles.actionBtn}
            onClick={onStart}
            disabled={!canStart}
            aria-label="Start wake listener"
          >
            Start
          </button>
          <button
            type="button"
            className={styles.actionBtnSecondary}
            onClick={onStop}
            disabled={!canStop}
            aria-label="Stop wake listener"
          >
            Stop
          </button>
          {showRetry ? (
            <button
              type="button"
              className={styles.actionBtnSecondary}
              onClick={onRetry}
              disabled={voicePending}
              aria-label="Retry starting wake listener"
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
