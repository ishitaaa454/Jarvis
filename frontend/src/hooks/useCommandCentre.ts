import { useCallback, useEffect, useState } from 'react';

import {
  fetchBrowserDestinations,
  fetchBrowserStatus,
  focusBrowserDestination,
  openBrowserDestination,
} from '../services/browserApi';
import { fetchHotkeyStatus, retryHotkeys } from '../services/hotkeyApi';
import {
  fetchRecentWindows,
  fetchWindowInventory,
  focusWindow,
  refreshWindowInventory,
  restoreWindow,
} from '../services/windowApi';
import type { BrowserDestination, BrowserStatus } from '../types/browser';
import type { HotkeyStatus } from '../types/hotkey';
import type { WebSocketMessage } from '../types/messages';
import type {
  RecentWindowRecord,
  WindowFocusResult,
  WindowInventorySnapshot,
} from '../types/windows';

export interface UseCommandCentreResult {
  inventory: WindowInventorySnapshot | null;
  recent: RecentWindowRecord[];
  hotkey: HotkeyStatus | null;
  browserStatus: BrowserStatus | null;
  destinations: BrowserDestination[];
  switchingLabel: string | null;
  error: string | null;
  loading: boolean;
  refresh: () => Promise<void>;
  focusWindowId: (windowId: string) => Promise<WindowFocusResult | null>;
  restoreWindowId: (windowId: string) => Promise<WindowFocusResult | null>;
  openDestination: (id: string) => Promise<void>;
  focusDestination: (id: string) => Promise<void>;
  retryHotkey: () => Promise<void>;
  handleSocketMessage: (message: WebSocketMessage) => void;
}

export function useCommandCentre(connected: boolean): UseCommandCentreResult {
  const [inventory, setInventory] = useState<WindowInventorySnapshot | null>(null);
  const [recent, setRecent] = useState<RecentWindowRecord[]>([]);
  const [hotkey, setHotkey] = useState<HotkeyStatus | null>(null);
  const [browserStatus, setBrowserStatus] = useState<BrowserStatus | null>(null);
  const [destinations, setDestinations] = useState<BrowserDestination[]>([]);
  const [switchingLabel, setSwitchingLabel] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const [inv, rec, hk, bs, dest] = await Promise.all([
        fetchWindowInventory(),
        fetchRecentWindows(),
        fetchHotkeyStatus(),
        fetchBrowserStatus(),
        fetchBrowserDestinations(),
      ]);
      setInventory(inv);
      setRecent(rec.recent ?? []);
      setHotkey(hk);
      setBrowserStatus(bs);
      setDestinations(dest.destinations ?? []);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Command centre unavailable');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    if (connected) void refresh();
  }, [connected, refresh]);

  const focusWindowId = useCallback(
    async (windowId: string) => {
      try {
        const group = inventory?.applications.find((app) =>
          app.windows.some((w) => w.window_id === windowId),
        );
        setSwitchingLabel(group ? `SWITCHING TO ${group.display_name.toUpperCase()}` : 'SWITCHING…');
        const result = await focusWindow(windowId);
        if (result.result === 'WINDOW_NOT_FOUND') {
          await refreshWindowInventory();
          await refresh();
        } else {
          await refresh();
        }
        return result;
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Focus failed');
        return null;
      } finally {
        setTimeout(() => setSwitchingLabel(null), 800);
      }
    },
    [inventory, refresh],
  );

  const restoreWindowId = useCallback(
    async (windowId: string) => {
      try {
        const result = await restoreWindow(windowId);
        await refresh();
        return result;
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Restore failed');
        return null;
      }
    },
    [refresh],
  );

  const openDestination = useCallback(
    async (id: string) => {
      await openBrowserDestination(id);
      await refresh();
    },
    [refresh],
  );

  const focusDestination = useCallback(
    async (id: string) => {
      await focusBrowserDestination(id);
      await refresh();
    },
    [refresh],
  );

  const retryHotkey = useCallback(async () => {
    const status = await retryHotkeys();
    setHotkey(status);
  }, []);

  const handleSocketMessage = useCallback((message: WebSocketMessage) => {
    try {
      if (message.type === 'windows.inventory_changed') {
        setInventory(message.payload as unknown as WindowInventorySnapshot);
      } else if (message.type === 'hotkey.status_changed') {
        setHotkey(message.payload as unknown as HotkeyStatus);
      } else if (message.type === 'browser.status_changed') {
        setBrowserStatus(message.payload as unknown as BrowserStatus);
      } else if (
        message.type === 'browser.destination_opened' ||
        message.type === 'browser.destination_focused'
      ) {
        void fetchBrowserDestinations().then((body) => setDestinations(body.destinations ?? []));
      } else if (message.type === 'hotkey.triggered') {
        /* timeline handled elsewhere */
      }
    } catch {
      /* ignore */
    }
  }, []);

  return {
    inventory,
    recent,
    hotkey,
    browserStatus,
    destinations,
    switchingLabel,
    error,
    loading,
    refresh,
    focusWindowId,
    restoreWindowId,
    openDestination,
    focusDestination,
    retryHotkey,
    handleSocketMessage,
  };
}
