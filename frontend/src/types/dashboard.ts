export type DashboardPanelId = 'applications' | 'core' | 'system';

export type TimelineCategory =
  | 'SYSTEM'
  | 'VOICE'
  | 'SPEECH'
  | 'WORKSPACE'
  | 'APPLICATION'
  | 'CONNECTION'
  | 'ERROR';

export type TimelineSeverity = 'INFO' | 'SUCCESS' | 'WARNING' | 'ERROR';

export interface TimelineEntry {
  id: string;
  timestamp: string;
  category: TimelineCategory;
  severity: TimelineSeverity;
  message: string;
  applicationId?: string;
  progress?: { completed: number; total: number };
}

export interface MetricSample {
  timestamp: number;
  cpuPercent: number;
  memoryPercent: number;
}

export interface MetricHistoryState {
  samples: MetricSample[];
  capacity: number;
}

export interface DashboardAnnouncement {
  id: string;
  message: string;
  politeness: 'polite' | 'assertive';
}

export const PANEL_ORDER: DashboardPanelId[] = ['applications', 'core', 'system'];

export const PANEL_ROUTES: Record<DashboardPanelId, string> = {
  applications: '/applications',
  core: '/',
  system: '/system',
};

export const PANEL_LABELS: Record<DashboardPanelId, string> = {
  applications: 'Applications',
  core: 'Core',
  system: 'System',
};

export function panelFromPath(pathname: string): DashboardPanelId | null {
  if (pathname === '/applications') return 'applications';
  if (pathname === '/system') return 'system';
  if (pathname === '/' || pathname === '') return 'core';
  return null;
}

export function panelIndex(id: DashboardPanelId): number {
  return PANEL_ORDER.indexOf(id);
}

/** 12-hour local clock formatting preference for the dashboard. */
export const CLOCK_HOUR12 = true;
