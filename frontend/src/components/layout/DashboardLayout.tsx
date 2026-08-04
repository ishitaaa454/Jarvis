import type { ReactNode } from 'react';
import { Link, useLocation } from 'react-router-dom';

import { NavigationDots } from './NavigationDots';
import type { ConnectionStatus } from '../../types/assistant';
import { ConnectionIndicator } from '../common/ConnectionIndicator';
import styles from './DashboardLayout.module.css';

interface DashboardLayoutProps {
  children: ReactNode;
  connectionStatus: ConnectionStatus;
}

const NAV_ITEMS = [
  { to: '/', label: 'Home' },
  { to: '/system', label: 'System' },
  { to: '/applications', label: 'Applications' },
  { to: '/settings', label: 'Settings' },
];

export function DashboardLayout({
  children,
  connectionStatus,
}: DashboardLayoutProps) {
  const location = useLocation();

  return (
    <div className={styles.shell}>
      <header className={styles.header}>
        <div>
          <p className={styles.brandMark}>JW</p>
          <p className={styles.brandSub}>PHASE 1 FOUNDATION</p>
        </div>
        <nav className={styles.nav} aria-label="Primary">
          {NAV_ITEMS.map((item) => {
            const active = location.pathname === item.to;
            return (
              <Link
                key={item.to}
                to={item.to}
                className={`${styles.navLink} ${active ? styles.navLinkActive : ''}`}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>
        <ConnectionIndicator status={connectionStatus} />
      </header>

      <main className={`${styles.main} anim-fade-in`}>{children}</main>

      <footer className={styles.footer}>
        <NavigationDots items={NAV_ITEMS} />
      </footer>
    </div>
  );
}
