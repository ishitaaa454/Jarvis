import { useEffect, useState } from 'react';

import { MetricCard } from '../components/common/MetricCard';
import { describeTtsStatus } from '../hooks/useSpeechStatus';
import { describeVoiceStatus } from '../hooks/useVoiceStatus';
import { environment } from '../config/environment';
import { fetchHealth } from '../services/api';
import type { TtsStatus } from '../types/speech';
import type { VoiceStatus } from '../types/voice';
import styles from './SystemPage.module.css';

const LATER = 'Available in a later phase';

interface SystemPageProps {
  voiceStatus: VoiceStatus | null;
  ttsStatus: TtsStatus | null;
}

export function SystemPage({ voiceStatus, ttsStatus }: SystemPageProps) {
  const [cpu, setCpu] = useState<number | null>(null);
  const [memory, setMemory] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      try {
        const health = await fetchHealth();
        if (cancelled) return;
        setCpu(health.system.cpu_percent);
        setMemory(health.system.memory_percent);
        setError(null);
      } catch {
        if (!cancelled) setError('Unable to reach /api/health');
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    void load();
    const id = window.setInterval(() => void load(), environment.healthPollIntervalMs);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, []);

  const micActive =
    voiceStatus?.status === 'LISTENING' || voiceStatus?.status === 'ACTIVATION_DETECTED';
  const micLabel = !voiceStatus
    ? 'Unknown'
    : micActive
      ? 'Active'
      : voiceStatus.microphone?.name
        ? 'Idle'
        : 'Unavailable';

  const modelLabel =
    voiceStatus?.status === 'MODEL_MISSING'
      ? 'Missing'
      : voiceStatus?.model_loaded
        ? 'Loaded'
        : 'Not loaded';

  const piperLabel = describeTtsStatus(ttsStatus?.status);
  const britishModel =
    ttsStatus?.status === 'MODEL_MISSING'
      ? 'Missing'
      : ttsStatus?.model_loaded
        ? 'Loaded'
        : 'Not loaded';
  const outputLabel =
    ttsStatus?.status === 'OUTPUT_UNAVAILABLE'
      ? 'Unavailable'
      : ttsStatus?.output_device?.name
        ? 'Available'
        : 'Unavailable';
  const playbackLabel =
    ttsStatus?.status === 'ERROR'
      ? 'Error'
      : ttsStatus?.is_speaking || ttsStatus?.status === 'SPEAKING'
        ? 'Speaking'
        : 'Idle';
  const suppression = ttsStatus?.microphone_suppressed ? 'Active' : 'Inactive';

  return (
    <div className={styles.page}>
      <header>
        <h1 className="page-title">SYSTEM</h1>
        <p className="page-subtitle">Host telemetry</p>
      </header>

      <div className={styles.grid}>
        <MetricCard
          title="CPU"
          value={cpu === null ? null : cpu.toFixed(1)}
          unit="%"
          loading={loading}
          error={error}
        />
        <MetricCard
          title="Memory"
          value={memory === null ? null : memory.toFixed(1)}
          unit="%"
          loading={loading}
          error={error}
        />
        <MetricCard title="GPU" value={null} placeholder={LATER} />
        <MetricCard title="Disk" value={null} placeholder={LATER} />
        <MetricCard title="Network" value={null} placeholder={LATER} />
        <MetricCard title="Battery" value={null} placeholder={LATER} />
        <MetricCard title="Running processes" value={null} placeholder={LATER} />
      </div>

      <section className={`glass-panel ${styles.voiceTable}`} aria-labelledby="voice-components">
        <h2 id="voice-components">Voice components</h2>
        <table>
          <thead>
            <tr>
              <th scope="col">Component</th>
              <th scope="col">Status</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>Microphone</td>
              <td>{micLabel}</td>
            </tr>
            <tr>
              <td>Wake listener</td>
              <td>{describeVoiceStatus(voiceStatus?.status)}</td>
            </tr>
            <tr>
              <td>Vosk model</td>
              <td>{modelLabel}</td>
            </tr>
            <tr>
              <td>Piper engine</td>
              <td>{piperLabel}</td>
            </tr>
            <tr>
              <td>British voice model</td>
              <td>{britishModel}</td>
            </tr>
            <tr>
              <td>Audio output</td>
              <td>{outputLabel}</td>
            </tr>
            <tr>
              <td>Speech playback</td>
              <td>{playbackLabel}</td>
            </tr>
            <tr>
              <td>Microphone suppression</td>
              <td>{suppression}</td>
            </tr>
            <tr>
              <td>Voice processing</td>
              <td>Local / Offline</td>
            </tr>
          </tbody>
        </table>
      </section>
    </div>
  );
}
