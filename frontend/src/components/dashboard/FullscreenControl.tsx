import { useFullscreen } from '../../hooks/useFullscreen';
import styles from './FullscreenControl.module.css';

export function FullscreenControl() {
  const { isFullscreen, supported, error, toggle } = useFullscreen();

  return (
    <div className={styles.wrap}>
      <button
        type="button"
        className={styles.button}
        onClick={() => void toggle()}
        disabled={!supported}
        aria-pressed={isFullscreen}
        title={
          supported
            ? isFullscreen
              ? 'Exit fullscreen'
              : 'Enter fullscreen (requires a user click)'
            : 'Fullscreen is not supported in this browser'
        }
      >
        {isFullscreen ? 'Exit Fullscreen' : 'Enter Fullscreen'}
      </button>
      {!supported && (
        <span className={styles.hint}>Fullscreen unavailable in this browser</span>
      )}
      {error && <span className={styles.error}>{error}</span>}
    </div>
  );
}
