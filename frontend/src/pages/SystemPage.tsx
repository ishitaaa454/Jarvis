import { useEffect, useState } from 'react';

import { MetricCard } from '../components/common/MetricCard';
import { environment } from '../config/environment';
import { fetchHealth } from '../services/api';
import styles from './SystemPage.module.css';

const LATER = 'Available in a later phase';

export function SystemPage() {
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
    </div>
  );
}
