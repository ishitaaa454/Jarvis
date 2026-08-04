import { useEffect, useState } from 'react';

import { MetricCard } from '../components/common/MetricCard';
import { describeVoiceStatus } from '../hooks/useVoiceStatus';
import { environment } from '../config/environment';
import { fetchHealth } from '../services/api';
import type { VoiceStatus } from '../types/voice';
import styles from './SystemPage.module.css';

const LATER = 'Available in a later phase';

interface SystemPageProps {
  voiceStatus: VoiceStatus | null;
}

export function SystemPage({ voiceStatus }: SystemPageProps) {
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
              <td>Voice processing</td>
              <td>Local / Offline</td>
            </tr>
          </tbody>
        </table>
      </section>
    </div>
  );
}
