import { useEffect, useState } from 'react';

import { ActivityLog } from '../components/jarvis/ActivityLog';
import { JarvisCorePlaceholder } from '../components/jarvis/JarvisCorePlaceholder';
import { MetricCard } from '../components/common/MetricCard';
import { StatusBadge } from '../components/common/StatusBadge';
import { WelcomeSequencePanel } from '../components/speech/WelcomeSequencePanel';
import { VoiceActivationBanner } from '../components/voice/VoiceActivationBanner';
import { WakeListenerPanel } from '../components/voice/WakeListenerPanel';
import { environment } from '../config/environment';
import { fetchHealth } from '../services/api';
import type { ConnectionStatus } from '../types/assistant';
import type { ActivityEntry } from '../types/messages';
import type { TtsStatus, UtteranceProgress } from '../types/speech';
import type { VoiceStatus } from '../types/voice';
import styles from './HomePage.module.css';

interface HomePageProps {
  connectionStatus: ConnectionStatus;
  assistantState: string | null;
  activity: ActivityEntry[];
  voiceStatus: VoiceStatus | null;
  voiceLoading: boolean;
  voiceError: string | null;
  voicePending: boolean;
  activationVisible: boolean;
  onStartListener: () => void;
  onStopListener: () => void;
  ttsStatus: TtsStatus | null;
  ttsLoading: boolean;
  ttsError: string | null;
  ttsPending: boolean;
  currentUtterance: UtteranceProgress | null;
  initializingVisible: boolean;
  sequenceCompleteVisible: boolean;
  speaking: boolean;
  onTestWelcome: () => void;
  onCancelSpeech: () => void;
  onRetryTts: () => void;
}

export function HomePage({
  connectionStatus,
  assistantState,
  activity,
  voiceStatus,
  voiceLoading,
  voiceError,
  voicePending,
  activationVisible,
  onStartListener,
  onStopListener,
  ttsStatus,
  ttsLoading,
  ttsError,
  ttsPending,
  currentUtterance,
  initializingVisible,
  sequenceCompleteVisible,
  speaking,
  onTestWelcome,
  onCancelSpeech,
  onRetryTts,
}: HomePageProps) {
  const [now, setNow] = useState(() => new Date());
  const [cpu, setCpu] = useState<number | null>(null);
  const [memory, setMemory] = useState<number | null>(null);
  const [healthLoading, setHealthLoading] = useState(true);
  const [healthError, setHealthError] = useState<string | null>(null);

  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 1000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    let cancelled = false;

    const loadHealth = async () => {
      try {
        const health = await fetchHealth();
        if (cancelled) return;
        setCpu(health.system.cpu_percent);
        setMemory(health.system.memory_percent);
        setHealthError(null);
      } catch {
        if (cancelled) return;
        setHealthError('Unable to reach /api/health');
      } finally {
        if (!cancelled) setHealthLoading(false);
      }
    };

    void loadHealth();
    const interval = window.setInterval(
      () => void loadHealth(),
      environment.healthPollIntervalMs,
    );
    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, []);

  const connected = connectionStatus === 'CONNECTED';

  return (
    <div className={styles.page}>
      <header className={styles.hero}>
        <h1 className={styles.heading}>JARVIS WORKSPACE</h1>
        <p className={styles.subheading}>PERSONAL SYSTEM INTERFACE</p>
      </header>

      <VoiceActivationBanner visible={activationVisible} />

      <div className={styles.coreWrap}>
        <JarvisCorePlaceholder
          connected={connected}
          activated={activationVisible || speaking}
        />
      </div>

      <section className={styles.statusRow}>
        <StatusBadge label="Connection" value={connectionStatus} tone="accent" />
        <StatusBadge
          label="Jarvis State"
          value={assistantState ?? (healthLoading ? 'Loading…' : 'Unknown')}
          tone={assistantState ? 'accent' : 'warning'}
        />
        <StatusBadge label="Local Time" value={now.toLocaleTimeString()} />
      </section>

      <WakeListenerPanel
        voiceStatus={voiceStatus}
        loading={voiceLoading}
        error={voiceError}
        pending={voicePending}
        onStart={onStartListener}
        onStop={onStopListener}
      />

      <WelcomeSequencePanel
        ttsStatus={ttsStatus}
        loading={ttsLoading}
        error={ttsError}
        pending={ttsPending}
        currentUtterance={currentUtterance}
        initializingVisible={initializingVisible}
        sequenceCompleteVisible={sequenceCompleteVisible}
        speaking={speaking}
        onTestWelcome={onTestWelcome}
        onCancel={onCancelSpeech}
        onRetry={onRetryTts}
      />

      <section className={styles.metrics}>
        <MetricCard
          title="CPU"
          value={cpu === null ? null : cpu.toFixed(1)}
          unit="%"
          loading={healthLoading}
          error={healthError}
        />
        <MetricCard
          title="Memory"
          value={memory === null ? null : memory.toFixed(1)}
          unit="%"
          loading={healthLoading}
          error={healthError}
        />
      </section>

      <ActivityLog entries={activity} />
    </div>
  );
}
