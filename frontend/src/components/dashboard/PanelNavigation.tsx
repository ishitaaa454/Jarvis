import type { UsePanelNavigationResult } from '../../hooks/usePanelNavigation';
import { PANEL_ORDER, type DashboardPanelId } from '../../types/dashboard';
import styles from './PanelNavigation.module.css';

interface Props {
  navigation: UsePanelNavigationResult;
}

export function PanelNavigation({ navigation }: Props) {
  return (
    <nav className={styles.nav} aria-label="Dashboard panels">
      <button
        type="button"
        className={styles.arrow}
        onClick={navigation.goPrevious}
        disabled={!navigation.canGoPrevious}
        aria-label="Previous panel"
      >
        ←
      </button>
      <div className={styles.dots} role="tablist" aria-label="Panel selection">
        {PANEL_ORDER.map((panel) => (
          <PanelDot
            key={panel}
            panel={panel}
            active={navigation.activePanel === panel}
            label={navigation.labels[panel]}
            onSelect={navigation.goTo}
          />
        ))}
      </div>
      <button
        type="button"
        className={styles.arrow}
        onClick={navigation.goNext}
        disabled={!navigation.canGoNext}
        aria-label="Next panel"
      >
        →
      </button>
      <div className={styles.labels}>
        {PANEL_ORDER.map((panel) => (
          <button
            key={panel}
            type="button"
            className={`${styles.labelBtn} ${
              navigation.activePanel === panel ? styles.labelActive : ''
            }`}
            onClick={() => navigation.goTo(panel)}
            aria-current={navigation.activePanel === panel ? 'page' : undefined}
          >
            {navigation.labels[panel]}
          </button>
        ))}
      </div>
    </nav>
  );
}

function PanelDot({
  panel,
  active,
  label,
  onSelect,
}: {
  panel: DashboardPanelId;
  active: boolean;
  label: string;
  onSelect: (panel: DashboardPanelId) => void;
}) {
  return (
    <button
      type="button"
      role="tab"
      aria-selected={active}
      aria-label={label}
      className={`${styles.dot} ${active ? styles.dotActive : ''}`}
      onClick={() => onSelect(panel)}
    />
  );
}
