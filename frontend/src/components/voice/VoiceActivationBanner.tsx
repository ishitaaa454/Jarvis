import styles from './VoiceActivationBanner.module.css';

interface VoiceActivationBannerProps {
  visible: boolean;
}

export function VoiceActivationBanner({ visible }: VoiceActivationBannerProps) {
  return (
    <div
      className={`${styles.banner} ${visible ? styles.visible : ''}`}
      role="status"
      aria-live="assertive"
      aria-hidden={!visible}
    >
      <span className={styles.label}>VOICE ACTIVATION CONFIRMED</span>
    </div>
  );
}
