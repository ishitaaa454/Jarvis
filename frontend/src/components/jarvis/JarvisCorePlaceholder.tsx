import styles from './JarvisCorePlaceholder.module.css';

interface JarvisCorePlaceholderProps {
  connected: boolean;
  activated?: boolean;
}

export function JarvisCorePlaceholder({
  connected,
  activated = false,
}: JarvisCorePlaceholderProps) {
  const className = [
    styles.core,
    connected ? styles.connected : styles.disconnected,
    activated ? styles.activated : '',
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <div className={className} aria-label="Jarvis core placeholder">
      <div className={styles.ring} />
      <div className={styles.ringInner} />
      <div className={styles.center}>
        <span>JW</span>
      </div>
    </div>
  );
}
