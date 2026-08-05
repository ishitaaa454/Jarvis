import { useCallback, useEffect, useRef } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';

import {
  PANEL_LABELS,
  PANEL_ORDER,
  PANEL_ROUTES,
  panelFromPath,
  panelIndex,
  type DashboardPanelId,
} from '../types/dashboard';

export interface UsePanelNavigationResult {
  activePanel: DashboardPanelId;
  activeIndex: number;
  labels: typeof PANEL_LABELS;
  goTo: (panel: DashboardPanelId) => void;
  goNext: () => void;
  goPrevious: () => void;
  goHome: () => void;
  canGoNext: boolean;
  canGoPrevious: boolean;
}

export function usePanelNavigation(): UsePanelNavigationResult {
  const location = useLocation();
  const navigate = useNavigate();
  const activePanel = panelFromPath(location.pathname) ?? 'core';
  const activeIndex = panelIndex(activePanel);

  const goTo = useCallback(
    (panel: DashboardPanelId) => {
      const route = PANEL_ROUTES[panel];
      if (location.pathname !== route) {
        navigate(route);
      }
    },
    [location.pathname, navigate],
  );

  const goNext = useCallback(() => {
    if (activeIndex < PANEL_ORDER.length - 1) {
      goTo(PANEL_ORDER[activeIndex + 1]);
    }
  }, [activeIndex, goTo]);

  const goPrevious = useCallback(() => {
    if (activeIndex > 0) {
      goTo(PANEL_ORDER[activeIndex - 1]);
    }
  }, [activeIndex, goTo]);

  const goHome = useCallback(() => goTo('core'), [goTo]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (
        target &&
        (target.tagName === 'INPUT' ||
          target.tagName === 'TEXTAREA' ||
          target.tagName === 'SELECT' ||
          target.isContentEditable)
      ) {
        return;
      }
      if (event.key === 'ArrowRight') {
        event.preventDefault();
        goNext();
      } else if (event.key === 'ArrowLeft') {
        event.preventDefault();
        goPrevious();
      } else if (event.key === 'Home') {
        event.preventDefault();
        goHome();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [goHome, goNext, goPrevious]);

  return {
    activePanel,
    activeIndex,
    labels: PANEL_LABELS,
    goTo,
    goNext,
    goPrevious,
    goHome,
    canGoNext: activeIndex < PANEL_ORDER.length - 1,
    canGoPrevious: activeIndex > 0,
  };
}

export interface PointerSwipeOptions {
  onSwipeLeft: () => void;
  onSwipeRight: () => void;
  onDragOffset?: (offsetPx: number) => void;
  onDragEnd?: () => void;
  thresholdPx?: number;
  enabled?: boolean;
}

export function usePointerSwipe(
  elementRef: React.RefObject<HTMLElement | null>,
  options: PointerSwipeOptions,
) {
  const {
    onSwipeLeft,
    onSwipeRight,
    onDragOffset,
    onDragEnd,
    thresholdPx = 72,
    enabled = true,
  } = options;
  const startRef = useRef<{ x: number; y: number; t: number; pointerId: number } | null>(
    null,
  );
  const draggingRef = useRef(false);
  const optionsRef = useRef(options);
  optionsRef.current = options;

  useEffect(() => {
    const el = elementRef.current;
    if (!el || !enabled) return;

    const isInteractive = (target: EventTarget | null) => {
      if (!(target instanceof Element)) return false;
      return Boolean(
        target.closest(
          'button, a, input, textarea, select, [role="button"], [data-no-swipe]',
        ),
      );
    };

    const onPointerDown = (event: PointerEvent) => {
      if (event.button !== 0) return;
      if (isInteractive(event.target)) return;
      const selection = window.getSelection();
      if (selection && selection.toString().length > 0) return;
      startRef.current = {
        x: event.clientX,
        y: event.clientY,
        t: performance.now(),
        pointerId: event.pointerId,
      };
      draggingRef.current = false;
      try {
        el.setPointerCapture(event.pointerId);
      } catch {
        /* ignore */
      }
    };

    const onPointerMove = (event: PointerEvent) => {
      const start = startRef.current;
      if (!start || event.pointerId !== start.pointerId) return;
      const dx = event.clientX - start.x;
      const dy = event.clientY - start.y;
      if (!draggingRef.current) {
        if (Math.abs(dx) < 8 && Math.abs(dy) < 8) return;
        if (Math.abs(dy) > Math.abs(dx)) {
          startRef.current = null;
          onDragEnd?.();
          return;
        }
        draggingRef.current = true;
      }
      onDragOffset?.(dx);
    };

    const finish = (event: PointerEvent) => {
      const start = startRef.current;
      if (!start || event.pointerId !== start.pointerId) return;
      const dx = event.clientX - start.x;
      const dy = event.clientY - start.y;
      const dt = Math.max(1, performance.now() - start.t);
      const velocity = Math.abs(dx) / dt;
      startRef.current = null;
      draggingRef.current = false;
      try {
        el.releasePointerCapture(event.pointerId);
      } catch {
        /* ignore */
      }
      onDragEnd?.();
      if (Math.abs(dy) > Math.abs(dx) * 1.2) return;
      const passed = Math.abs(dx) >= thresholdPx || (Math.abs(dx) > 40 && velocity > 0.45);
      if (!passed) return;
      if (dx < 0) onSwipeLeft();
      else onSwipeRight();
    };

    const onPointerCancel = (event: PointerEvent) => {
      if (!startRef.current || event.pointerId !== startRef.current.pointerId) return;
      startRef.current = null;
      draggingRef.current = false;
      onDragEnd?.();
    };

    el.addEventListener('pointerdown', onPointerDown);
    el.addEventListener('pointermove', onPointerMove);
    el.addEventListener('pointerup', finish);
    el.addEventListener('pointercancel', onPointerCancel);
    return () => {
      el.removeEventListener('pointerdown', onPointerDown);
      el.removeEventListener('pointermove', onPointerMove);
      el.removeEventListener('pointerup', finish);
      el.removeEventListener('pointercancel', onPointerCancel);
    };
  }, [elementRef, enabled, onDragEnd, onDragOffset, onSwipeLeft, onSwipeRight, thresholdPx]);
}
