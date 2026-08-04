import styles from './JarvisCorePlaceholder.module.css';

interface JarvisCorePlaceholderProps {
  connected: boolean;
}

export function JarvisCorePlaceholder({ connected }: JarvisCorePlaceholderProps) {
  return (
    <div
      className={`${styles.core} ${connected ? styles.connected : styles.disconnected}`}
      aria-label="Jarvis core placeholder"
    >
      <div className={styles.ring} />
      <div className={styles.ringInner} />
      <div className={styles.center}>
        <span>JW</span>
      </div>
    </div>
  );
}
