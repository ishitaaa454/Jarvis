import { Link, useLocation } from 'react-router-dom';

import styles from './NavigationDots.module.css';

interface NavItem {
  to: string;
  label: string;
}

interface NavigationDotsProps {
  items: NavItem[];
}

export function NavigationDots({ items }: NavigationDotsProps) {
  const location = useLocation();

  return (
    <div className={styles.row} role="navigation" aria-label="Page indicators">
      {items.map((item) => {
        const active = location.pathname === item.to;
        return (
          <Link
            key={item.to}
            to={item.to}
            className={`${styles.dot} ${active ? styles.active : ''}`}
            title={item.label}
            aria-label={item.label}
            aria-current={active ? 'page' : undefined}
          />
        );
      })}
    </div>
  );
}
