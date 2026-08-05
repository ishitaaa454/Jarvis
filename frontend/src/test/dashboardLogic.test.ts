import { describe, expect, it } from 'vitest';

import { activityReducer, makeTimelineId, trimTimeline } from '../reducers/activityReducer';
import {
  createMetricHistory,
  metricBounds,
  metricHistoryReducer,
} from '../reducers/metricHistoryReducer';
import { dispatchDashboardEvent } from '../services/dashboardEventDispatcher';
import { mapAssistantToCoreState } from '../components/core/JarvisCore';
import { panelFromPath, PANEL_ORDER } from '../types/dashboard';
import type { TimelineEntry } from '../types/dashboard';

describe('panel routes', () => {
  it('maps core as default', () => {
    expect(panelFromPath('/')).toBe('core');
    expect(panelFromPath('')).toBe('core');
  });

  it('maps applications and system', () => {
    expect(panelFromPath('/applications')).toBe('applications');
    expect(panelFromPath('/system')).toBe('system');
  });

  it('keeps panel boundaries', () => {
    expect(PANEL_ORDER[0]).toBe('applications');
    expect(PANEL_ORDER[1]).toBe('core');
    expect(PANEL_ORDER[2]).toBe('system');
  });
});

describe('core state mapping', () => {
  it('maps assistant states', () => {
    expect(mapAssistantToCoreState('LISTENING', true)).toBe('listening');
    expect(mapAssistantToCoreState('PROCESSING', true)).toBe('processing');
    expect(mapAssistantToCoreState('SPEAKING', true)).toBe('speaking');
    expect(mapAssistantToCoreState('OPENING_APPLICATIONS', true)).toBe('opening');
    expect(mapAssistantToCoreState('READY', true)).toBe('ready');
    expect(mapAssistantToCoreState('ERROR', true)).toBe('error');
    expect(mapAssistantToCoreState('LISTENING', false)).toBe('offline');
  });
});

describe('metric history', () => {
  it('bounds history capacity', () => {
    let state = createMetricHistory(3);
    for (let i = 0; i < 5; i += 1) {
      state = metricHistoryReducer(state, {
        type: 'push',
        sample: { timestamp: i, cpuPercent: i, memoryPercent: i },
      });
    }
    expect(state.samples).toHaveLength(3);
    expect(state.samples[0].cpuPercent).toBe(2);
  });

  it('handles empty and constant bounds', () => {
    expect(metricBounds([])).toEqual({ min: 0, max: 0 });
    expect(metricBounds([4, 4, 4])).toEqual({ min: 4, max: 4 });
  });
});

describe('timeline', () => {
  it('deduplicates by id', () => {
    const entry: TimelineEntry = {
      id: 'a',
      timestamp: '2026-01-01T00:00:00.000Z',
      category: 'SYSTEM',
      severity: 'INFO',
      message: 'hello',
    };
    const once = activityReducer([], { type: 'append', entry });
    const twice = activityReducer(once, { type: 'append', entry });
    expect(twice).toHaveLength(1);
  });

  it('trims while preferring errors', () => {
    const entries: TimelineEntry[] = Array.from({ length: 30 }, (_, i) => ({
      id: `i-${i}`,
      timestamp: `2026-01-01T00:00:${String(i).padStart(2, '0')}.000Z`,
      category: i === 0 ? 'ERROR' : 'SYSTEM',
      severity: i === 0 ? 'ERROR' : 'INFO',
      message: `m-${i}`,
    }));
    const trimmed = trimTimeline(entries, 5);
    expect(trimmed.length).toBeLessThanOrEqual(5);
    expect(trimmed.some((e) => e.severity === 'ERROR')).toBe(true);
  });

  it('builds stable ids', () => {
    expect(makeTimelineId('state.changed', 't', 'READY')).toBe(
      'state.changed|t|READY',
    );
  });
});

describe('websocket dispatcher', () => {
  it('handles known events', () => {
    const wake = dispatchDashboardEvent({
      type: 'voice.wake_detected',
      timestamp: 't1',
      payload: { phrase: 'Wake up Jarvis', confidence: 0.9 },
    });
    expect(wake.announcement?.message.toLowerCase()).toContain('voice');
    expect(wake.timeline?.message).toContain('Wake');

    const speak = dispatchDashboardEvent({
      type: 'tts.utterance_started',
      timestamp: 't2',
      payload: { index: 1, total: 3, text: 'Hello' },
    });
    expect(speak.timeline?.progress).toEqual({ completed: 1, total: 3 });

    const opening = dispatchDashboardEvent({
      type: 'workspace.application_status',
      timestamp: 't3',
      payload: {
        application_id: 'vscode',
        display_name: 'Visual Studio Code',
        status: 'LAUNCHING',
        index: 1,
        total: 7,
      },
    });
    expect(opening.timeline?.message).toContain('Visual Studio Code');
  });

  it('ignores unknown and malformed payloads safely', () => {
    expect(() =>
      dispatchDashboardEvent({
        type: 'totally.unknown.event',
        timestamp: 't',
        payload: {},
      }),
    ).not.toThrow();

    expect(() =>
      dispatchDashboardEvent({
        type: 'workspace.application_result',
        timestamp: 't',
        payload: {},
      }),
    ).not.toThrow();
  });
});
