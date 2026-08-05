import type { AssistantState } from '../../types/assistant';
import styles from './JarvisCore.module.css';

export type CoreVisualState =
  | 'offline'
  | 'starting'
  | 'idle'
  | 'listening'
  | 'processing'
  | 'speaking'
  | 'initializing'
  | 'opening'
  | 'ready'
  | 'error'
  | 'shutdown';

export function mapAssistantToCoreState(
  state: AssistantState | null,
  connected: boolean,
): CoreVisualState {
  if (!connected) return 'offline';
  switch (state) {
    case 'OFFLINE':
      return 'offline';
    case 'STARTING':
      return 'starting';
    case 'IDLE':
      return 'idle';
    case 'LISTENING':
      return 'listening';
    case 'PROCESSING':
      return 'processing';
    case 'SPEAKING':
      return 'speaking';
    case 'INITIALIZING_WORKSPACE':
      return 'initializing';
    case 'OPENING_APPLICATIONS':
      return 'opening';
    case 'READY':
      return 'ready';
    case 'ERROR':
      return 'error';
    case 'SHUTTING_DOWN':
      return 'shutdown';
    default:
      return 'idle';
  }
}

interface Props {
  assistantState: AssistantState | null;
  connected: boolean;
  reducedMotion: boolean;
  tabVisible: boolean;
  progressRatio?: number | null;
  label: string;
}

export function JarvisCore({
  assistantState,
  connected,
  reducedMotion,
  tabVisible,
  progressRatio,
  label,
}: Props) {
  const visual = mapAssistantToCoreState(assistantState, connected);
  const progress = Math.max(0, Math.min(1, progressRatio ?? 0));
  const dash = 2 * Math.PI * 88;
  const offset = dash * (1 - progress);

  return (
    <div
      className={`${styles.core} ${styles[visual]} ${
        reducedMotion || !tabVisible ? styles.reduced : ''
      }`}
      role="img"
      aria-label={`Jarvis core: ${label}`}
    >
      <svg className={styles.svg} viewBox="0 0 240 240" aria-hidden="true">
        <defs>
          <radialGradient id="orbGlow" cx="50%" cy="45%" r="55%">
            <stop offset="0%" stopColor="rgba(154, 236, 255, 0.95)" />
            <stop offset="55%" stopColor="rgba(79, 210, 255, 0.35)" />
            <stop offset="100%" stopColor="rgba(79, 210, 255, 0)" />
          </radialGradient>
        </defs>
        <circle className={styles.outer} cx="120" cy="120" r="108" />
        <g className={styles.ringA}>
          <circle cx="120" cy="120" r="98" fill="none" stroke="rgba(79,210,255,0.28)" strokeWidth="1.2" strokeDasharray="6 10" />
        </g>
        <g className={styles.ringB}>
          <circle cx="120" cy="120" r="82" fill="none" stroke="rgba(154,236,255,0.22)" strokeWidth="1" strokeDasharray="2 8" />
        </g>
        <circle
          className={styles.progress}
          cx="120"
          cy="120"
          r="88"
          fill="none"
          stroke="var(--accent-primary)"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeDasharray={dash}
          strokeDashoffset={visual === 'opening' ? offset : dash * 0.15}
          transform="rotate(-90 120 120)"
        />
        {[...Array(24)].map((_, i) => {
          const angle = (i / 24) * Math.PI * 2;
          const x1 = 120 + Math.cos(angle) * 104;
          const y1 = 120 + Math.sin(angle) * 104;
          const x2 = 120 + Math.cos(angle) * 110;
          const y2 = 120 + Math.sin(angle) * 110;
          return (
            <line
              key={i}
              x1={x1}
              y1={y1}
              x2={x2}
              y2={y2}
              stroke="rgba(79,210,255,0.35)"
              strokeWidth="1"
            />
          );
        })}
        <circle className={styles.orb} cx="120" cy="120" r="42" fill="url(#orbGlow)" />
        <circle className={styles.orbCore} cx="120" cy="120" r="18" />
      </svg>
      <div className={styles.label}>{label}</div>
    </div>
  );
}
