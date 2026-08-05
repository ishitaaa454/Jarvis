import { useMemo, useRef, useState } from 'react';

import { useDashboard } from '../../context/DashboardContext';
import {
  usePanelNavigation,
  usePointerSwipe,
} from '../../hooks/usePanelNavigation';
import { PANEL_ORDER } from '../../types/dashboard';
import { ApplicationsCommandGrid } from '../applications/ApplicationCommandGrid';
import { CorePanel } from '../core/CorePanel';
import { SystemIntelligencePanel } from '../system/SystemIntelligencePanel';
import { GlobalStatusStrip } from './GlobalStatusStrip';
import { PanelNavigation } from './PanelNavigation';
import styles from './PanelViewport.module.css';

export function PanelViewport() {
  const navigation = usePanelNavigation();
  const { reducedMotion, tabVisible } = useDashboard();
  const viewportRef = useRef<HTMLDivElement>(null);
  const [dragOffset, setDragOffset] = useState(0);

  usePointerSwipe(viewportRef, {
    enabled: true,
    onSwipeLeft: navigation.goNext,
    onSwipeRight: navigation.goPrevious,
    onDragOffset: (dx) => {
      if (reducedMotion) return;
      setDragOffset(dx);
    },
    onDragEnd: () => setDragOffset(0),
  });

  const translate = useMemo(() => {
    const base = -navigation.activeIndex * 100;
    if (!dragOffset || reducedMotion) return `translate3d(${base}%, 0, 0)`;
    const width = viewportRef.current?.clientWidth || 1;
    const percent = (dragOffset / width) * 100;
    return `translate3d(calc(${base}% + ${percent}%), 0, 0)`;
  }, [navigation.activeIndex, dragOffset, reducedMotion]);

  return (
    <div className={`${styles.root} ${tabVisible ? '' : styles.hiddenTab}`}>
      <GlobalStatusStrip />
      <div
        className={styles.viewport}
        ref={viewportRef}
        data-testid="panel-viewport"
      >
        <div
          className={`${styles.track} ${reducedMotion ? styles.fadeMode : ''}`}
          style={{ transform: reducedMotion ? undefined : translate }}
          data-active={navigation.activePanel}
        >
          {PANEL_ORDER.map((panel) => (
            <section
              key={panel}
              className={`${styles.panel} ${
                navigation.activePanel === panel ? styles.panelActive : styles.panelHidden
              }`}
              aria-hidden={navigation.activePanel !== panel}
              data-panel={panel}
            >
              {panel === 'applications' && <ApplicationsCommandGrid />}
              {panel === 'core' && <CorePanel />}
              {panel === 'system' && <SystemIntelligencePanel />}
            </section>
          ))}
        </div>
      </div>
      <PanelNavigation navigation={navigation} />
    </div>
  );
}
