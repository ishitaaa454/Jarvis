import { useCallback, useEffect, useState } from 'react';

export interface UseFullscreenResult {
  isFullscreen: boolean;
  supported: boolean;
  error: string | null;
  enter: () => Promise<void>;
  exit: () => Promise<void>;
  toggle: () => Promise<void>;
}

export function useFullscreen(
  targetRef?: { current: HTMLElement | null },
): UseFullscreenResult {
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const supported =
    typeof document !== 'undefined' &&
    typeof document.documentElement.requestFullscreen === 'function';

  useEffect(() => {
    const onChange = () => {
      setIsFullscreen(Boolean(document.fullscreenElement));
    };
    document.addEventListener('fullscreenchange', onChange);
    return () => document.removeEventListener('fullscreenchange', onChange);
  }, []);

  const enter = useCallback(async () => {
    setError(null);
    if (!supported) {
      setError('Fullscreen is not supported in this browser.');
      return;
    }
    const el = targetRef?.current ?? document.documentElement;
    try {
      await el.requestFullscreen();
    } catch {
      setError('Unable to enter fullscreen. A user gesture is required.');
    }
  }, [supported, targetRef]);

  const exit = useCallback(async () => {
    setError(null);
    if (!document.fullscreenElement) return;
    try {
      await document.exitFullscreen();
    } catch {
      setError('Unable to exit fullscreen.');
    }
  }, []);

  const toggle = useCallback(async () => {
    if (document.fullscreenElement) await exit();
    else await enter();
  }, [enter, exit]);

  return { isFullscreen, supported, error, enter, exit, toggle };
}
