import { Link } from 'react-router-dom';
import type { ReactNode } from 'react';

import { useDashboard } from '../../context/DashboardContext';
import { FullscreenControl } from './FullscreenControl';
import { SystemClock } from './SystemClock';
import styles from './DashboardShell.module.css';

interface Props {
  children: ReactNode;
  mode?: 'panels' | 'settings';
}

export function DashboardShell({ children, mode = 'panels' }: Props) {
  const { connectionStatus, announcement, dataStale } = useDashboard();

  return (
    <div className={styles.shell}>
      <div className={styles.ambient} aria-hidden="true" />
      <header className={styles.header}>
        <div className={styles.brand}>
          <p className={styles.product}>JARVIS WORKSPACE</p>
          <p className={styles.sub}>PERSONAL SYSTEM INTERFACE</p>
        </div>
        <div className={styles.headerCenter}>
          <span
            className={`${styles.connection} ${styles[connectionStatus.toLowerCase()] ?? ''}`}
          >
            {connectionStatus}
            {dataStale ? ' · STALE' : ''}
          </span>
          <nav className={styles.links} aria-label="Primary">
            <Link to="/">Core</Link>
            <Link to="/applications">Applications</Link>
            <Link to="/system">System</Link>
            <Link to="/settings">Settings</Link>
          </nav>
        </div>
        <div className={styles.headerRight}>
          <FullscreenControl />
          <SystemClock />
        </div>
      </header>

      <div
        className={styles.live}
        aria-live={announcement?.politeness ?? 'polite'}
        aria-atomic="true"
      >
        {announcement?.message}
      </div>

      <main className={`${styles.main} ${mode === 'settings' ? styles.settingsMain : ''}`}>
        {children}
      </main>

      <footer className={styles.footer}>
        <span>Jarvis Workspace · Local / Offline processing</span>
        <span>v0.1.0</span>
      </footer>
    </div>
  );
}
