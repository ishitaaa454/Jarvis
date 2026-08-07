import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';

import { ApplicationCommandCentre } from '../components/command-centre/ApplicationCommandCentre';
import type { DashboardContextValue } from '../context/DashboardContext';
import { DashboardContext } from '../context/DashboardContext';
import { createMetricHistory } from '../reducers/metricHistoryReducer';

function mockDashboard(
  partial: Partial<DashboardContextValue> = {},
): DashboardContextValue {
  return {
    connectionStatus: 'CONNECTED',
    assistantState: 'READY',
    dataStale: false,
    connectedAt: null,
    health: null,
    healthError: null,
    metricHistory: createMetricHistory(),
    refreshHealth: vi.fn(),
    timeline: [],
    clearTimeline: vi.fn(),
    activity: [],
    announcement: null,
    tabVisible: true,
    reducedMotion: true,
    reducedMotionOverride: null,
    setReducedMotionOverride: vi.fn(),
    voice: {} as DashboardContextValue['voice'],
    speech: {} as DashboardContextValue['speech'],
    workspace: {
      openApp: vi.fn(),
      focusApp: vi.fn(),
      refresh: vi.fn(),
      applications: [],
      loading: false,
      pending: false,
      pendingAppIds: new Set(),
      error: null,
    } as unknown as DashboardContextValue['workspace'],
    systemMonitor: {
      snapshot: null,
      status: null,
      series: {},
      freshness: 'LIVE',
      refresh: vi.fn(),
      handleSocketMessage: vi.fn(),
    } as unknown as DashboardContextValue['systemMonitor'],
    commandCentre: {
      inventory: {
        applications: [
          {
            application_id: 'vscode',
            display_name: 'Visual Studio Code',
            running: true,
            window_count: 2,
            foreground: true,
            favourite: true,
            allow_preview: false,
            windows: [
              {
                window_id: 'win_a',
                application_id: 'vscode',
                process_id: 1,
                display_title: 'jarvis-workspace',
                visible: true,
                minimized: false,
                foreground: true,
                focusable: true,
                first_seen_at: null,
                last_seen_at: null,
                last_jarvis_focus_at: null,
              },
              {
                window_id: 'win_b',
                application_id: 'vscode',
                process_id: 1,
                display_title: 'README.md',
                visible: true,
                minimized: true,
                foreground: false,
                focusable: true,
                first_seen_at: null,
                last_seen_at: null,
                last_jarvis_focus_at: null,
              },
            ],
          },
          {
            application_id: 'teams',
            display_name: 'Microsoft Teams',
            running: true,
            window_count: 1,
            foreground: false,
            favourite: true,
            allow_preview: false,
            windows: [
              {
                window_id: 'win_t',
                application_id: 'teams',
                process_id: 2,
                display_title: 'Microsoft Teams',
                visible: true,
                minimized: false,
                foreground: false,
                focusable: true,
                first_seen_at: null,
                last_seen_at: null,
                last_jarvis_focus_at: null,
              },
            ],
          },
        ],
        total_windows: 3,
        running_applications: 2,
        foreground_application_id: 'vscode',
        foreground_window_id: 'win_a',
        collected_at: new Date().toISOString(),
        available: true,
        reason: null,
      },
      recent: [
        {
          window_id: 'win_a',
          application_id: 'vscode',
          display_name: 'Visual Studio Code',
          display_title: 'jarvis-workspace',
          last_foreground_at: new Date().toISOString(),
        },
      ],
      hotkey: {
        enabled: true,
        status: 'REGISTERED',
        shortcuts: [{ action: 'SHOW_DASHBOARD', display: 'Ctrl + Alt + J' }],
        last_triggered_at: null,
        conflict_message: null,
      },
      browserStatus: {
        enabled: true,
        status: 'CONNECTED',
        mode: 'session',
        cdp_enabled: false,
        exact_tab_focus_available: false,
        reason: 'Exact browser-tab switching unavailable',
      },
      destinations: [
        {
          id: 'gmail',
          display_name: 'Gmail',
          known_open: true,
          exact_focus_available: false,
          url: 'https://mail.google.com/',
          last_opened_at: null,
          last_focused_at: null,
        },
      ],
      switchingLabel: null,
      error: null,
      loading: false,
      refresh: vi.fn(),
      focusWindowId: vi.fn().mockResolvedValue({ result: 'FOCUSED' }),
      restoreWindowId: vi.fn().mockResolvedValue({ result: 'RESTORED' }),
      openDestination: vi.fn(),
      focusDestination: vi.fn(),
      retryHotkey: vi.fn(),
      handleSocketMessage: vi.fn(),
    } as DashboardContextValue['commandCentre'],
    ...partial,
  };
}

describe('ApplicationCommandCentre', () => {
  it('renders command centre with grouped windows and safe titles', async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <DashboardContext.Provider value={mockDashboard()}>
          <ApplicationCommandCentre />
        </DashboardContext.Provider>
      </MemoryRouter>,
    );
    expect(screen.getByTestId('applications-panel')).toBeInTheDocument();
    expect(screen.getByText(/Ctrl \+ Alt \+ J/i)).toBeInTheDocument();
    expect(screen.getByText(/Focus limited to Chrome window/i)).toBeInTheDocument();
    const groupHeaders = screen.getAllByRole('button', { name: /Visual Studio Code/i });
    await user.click(groupHeaders[groupHeaders.length - 1]);
    expect(screen.getAllByText('jarvis-workspace').length).toBeGreaterThan(0);
    expect(screen.getByText('README.md')).toBeInTheDocument();
    expect(screen.queryByText(/Inbox/i)).not.toBeInTheDocument();
  });

  it('filters by search on safe titles', async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <DashboardContext.Provider value={mockDashboard()}>
          <ApplicationCommandCentre />
        </DashboardContext.Provider>
      </MemoryRouter>,
    );
    await user.type(screen.getByPlaceholderText(/safe window titles/i), 'jarvis');
    expect(screen.getAllByText(/Visual Studio Code/i).length).toBeGreaterThan(0);
    expect(screen.queryByText(/Microsoft Teams/i)).not.toBeInTheDocument();
  });

  it('calls focus endpoint from window switch', async () => {
    const user = userEvent.setup();
    const value = mockDashboard();
    render(
      <MemoryRouter>
        <DashboardContext.Provider value={value}>
          <ApplicationCommandCentre />
        </DashboardContext.Provider>
      </MemoryRouter>,
    );
    const groupHeaders = screen.getAllByRole('button', { name: /Visual Studio Code/i });
    await user.click(groupHeaders[groupHeaders.length - 1]);
    const switchButtons = screen.getAllByRole('button', { name: 'Switch' });
    await user.click(switchButtons[0]);
    expect(value.commandCentre.focusWindowId).toHaveBeenCalled();
  });
});
