import { useMemo, useState } from 'react';

import { useDashboard } from '../../context/DashboardContext';
import styles from './ApplicationCommandCentre.module.css';

const INITIALS: Record<string, string> = {
  vscode: 'VS',
  chrome: 'CH',
  gmail: 'GM',
  teams: 'TM',
  whatsapp: 'WA',
  spotify: 'SP',
  news: 'NW',
  dashboard: 'JV',
};

function windowStateLabel(win: {
  foreground: boolean;
  minimized: boolean;
}): string {
  if (win.foreground) return 'ACTIVE';
  if (win.minimized) return 'MINIMIZED';
  return 'BACKGROUND';
}

export function ApplicationCommandCentre() {
  const { commandCentre, workspace } = useDashboard();
  const [query, setQuery] = useState('');
  const [expanded, setExpanded] = useState<string | null>(null);
  const inventory = commandCentre.inventory;
  const apps = inventory?.applications ?? [];

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return apps;
    return apps
      .map((app) => {
        const nameMatch = app.display_name.toLowerCase().includes(q);
        const windows = app.windows.filter((w) =>
          w.display_title.toLowerCase().includes(q),
        );
        if (nameMatch || windows.length) {
          return { ...app, windows: nameMatch ? app.windows : windows };
        }
        return null;
      })
      .filter(Boolean) as typeof apps;
  }, [apps, query]);

  const favourites = filtered.filter((app) => app.favourite);
  const others = filtered.filter((app) => !app.favourite);
  const foregroundApp = apps.find(
    (app) => app.application_id === inventory?.foreground_application_id,
  );
  const hotkeyDisplay =
    commandCentre.hotkey?.shortcuts[0]?.display ?? 'Ctrl + Alt + J';

  const onFavouriteClick = async (appId: string) => {
    const app = apps.find((item) => item.application_id === appId);
    if (!app) return;
    if (app.window_count === 1 && app.windows[0]) {
      await commandCentre.focusWindowId(app.windows[0].window_id);
      return;
    }
    if (app.window_count > 1) {
      setExpanded(appId);
      return;
    }
    await workspace.openApp(appId);
  };

  return (
    <div className={styles.root} data-testid="applications-panel">
      <header className={styles.header}>
        <div>
          <h2>Application Command Centre</h2>
          <p>
            {inventory?.total_windows ?? 0} windows ·{' '}
            {inventory?.running_applications ?? 0} apps running · Foreground:{' '}
            {foregroundApp?.display_name ?? '—'} · Return: {hotkeyDisplay}
          </p>
        </div>
        <button
          type="button"
          className={styles.refresh}
          data-no-swipe
          onClick={() => void commandCentre.refresh()}
        >
          Refresh
        </button>
      </header>

      {commandCentre.switchingLabel ? (
        <p className={styles.switching} role="status">
          {commandCentre.switchingLabel}
        </p>
      ) : null}
      {commandCentre.error ? <p className={styles.error}>{commandCentre.error}</p> : null}

      <label className={styles.search}>
        Search
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Applications or safe window titles"
          data-no-swipe
        />
      </label>

      <section className={styles.section}>
        <h3>Hotkey</h3>
        <p className={styles.meta}>
          {commandCentre.hotkey?.status ?? 'UNKNOWN'}
          {commandCentre.hotkey?.conflict_message
            ? ` — ${commandCentre.hotkey.conflict_message}`
            : ''}
        </p>
        {commandCentre.hotkey?.status === 'CONFLICT' ? (
          <button type="button" data-no-swipe onClick={() => void commandCentre.retryHotkey()}>
            Retry hotkey
          </button>
        ) : null}
      </section>

      <section className={styles.section}>
        <h3>Browser destinations</h3>
        <p className={styles.meta}>
          {commandCentre.browserStatus?.exact_tab_focus_available
            ? 'Exact tab focus available'
            : 'Focus limited to Chrome window (session mode)'}
        </p>
        <div className={styles.destGrid}>
          {commandCentre.destinations.map((dest) => (
            <article key={dest.id} className={styles.destCard} data-no-swipe>
              <div className={styles.icon}>{INITIALS[dest.id] ?? 'BR'}</div>
              <h4>{dest.display_name}</h4>
              <p className={styles.meta}>
                {dest.known_open ? 'Known open' : 'Unknown'} ·{' '}
                {dest.exact_focus_available ? 'Exact focus' : 'Limited focus'}
              </p>
              <div className={styles.actions}>
                <button type="button" onClick={() => void commandCentre.openDestination(dest.id)}>
                  Open
                </button>
                <button type="button" onClick={() => void commandCentre.focusDestination(dest.id)}>
                  Focus
                </button>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className={styles.section}>
        <h3>Favourites</h3>
        <div className={styles.grid}>
          {favourites.map((app) => (
            <button
              key={app.application_id}
              type="button"
              className={`${styles.card} ${app.foreground ? styles.active : ''}`}
              data-no-swipe
              onClick={() => void onFavouriteClick(app.application_id)}
            >
              <div className={styles.icon}>
                {INITIALS[app.application_id] ?? app.display_name.slice(0, 2)}
              </div>
              <h4>{app.display_name}</h4>
              <p className={styles.meta}>
                {app.running
                  ? app.window_count
                    ? `${app.window_count} WINDOW${app.window_count === 1 ? '' : 'S'}`
                    : 'RUNNING'
                  : 'READY TO LAUNCH'}
                {app.foreground ? ' · ACTIVE' : ''}
              </p>
            </button>
          ))}
        </div>
      </section>

      <section className={styles.section}>
        <h3>Recent</h3>
        <div className={styles.recent}>
          {commandCentre.recent.length === 0 ? (
            <p className={styles.meta}>No recent approved windows yet</p>
          ) : (
            commandCentre.recent.map((item) => (
              <button
                key={item.window_id}
                type="button"
                className={styles.recentItem}
                data-no-swipe
                onClick={() => void commandCentre.focusWindowId(item.window_id)}
              >
                <span>{INITIALS[item.application_id] ?? 'AP'}</span>
                <strong>{item.display_title}</strong>
              </button>
            ))
          )}
        </div>
      </section>

      <section className={styles.section}>
        <h3>Applications</h3>
        <div className={styles.groups}>
          {[...favourites, ...others].map((app) => {
            const open = expanded === app.application_id;
            return (
              <article key={app.application_id} className={styles.group} data-no-swipe>
                <button
                  type="button"
                  className={styles.groupHeader}
                  onClick={() =>
                    setExpanded(open ? null : app.application_id)
                  }
                >
                  <div className={styles.icon}>
                    {INITIALS[app.application_id] ?? app.display_name.slice(0, 2)}
                  </div>
                  <div>
                    <h4>{app.display_name}</h4>
                    <p className={styles.meta}>
                      {app.running ? 'ACTIVE' : 'READY'} · {app.window_count} windows
                      {app.foreground ? ' · FOREGROUND' : ''}
                    </p>
                  </div>
                </button>
                {open ? (
                  <ul className={styles.windowList}>
                    {app.windows.length === 0 ? (
                      <li className={styles.meta}>No windows detected</li>
                    ) : (
                      app.windows.map((win) => (
                        <li key={win.window_id}>
                          <div>
                            <strong>{win.display_title}</strong>
                            <span>{windowStateLabel(win)}</span>
                          </div>
                          <div className={styles.actions}>
                            {win.minimized ? (
                              <button
                                type="button"
                                onClick={() => void commandCentre.restoreWindowId(win.window_id)}
                              >
                                Restore
                              </button>
                            ) : null}
                            <button
                              type="button"
                              onClick={() => void commandCentre.focusWindowId(win.window_id)}
                            >
                              Switch
                            </button>
                          </div>
                        </li>
                      ))
                    )}
                    {!app.running ? (
                      <li>
                        <button
                          type="button"
                          onClick={() => void workspace.openApp(app.application_id)}
                        >
                          Launch
                        </button>
                      </li>
                    ) : null}
                  </ul>
                ) : null}
              </article>
            );
          })}
        </div>
      </section>
    </div>
  );
}
