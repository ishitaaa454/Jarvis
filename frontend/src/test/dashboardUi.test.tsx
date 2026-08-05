import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { PanelNavigation } from '../components/dashboard/PanelNavigation';
import { mapAssistantToCoreState, JarvisCore } from '../components/core/JarvisCore';
import { ActivationSequence } from '../components/core/ActivationSequence';
import { usePanelNavigation } from '../hooks/usePanelNavigation';
import type { DashboardContextValue } from '../context/DashboardContext';
import { DashboardContext } from '../context/DashboardContext';
import { createMetricHistory } from '../reducers/metricHistoryReducer';

vi.mock('../hooks/useJarvisSocket', () => ({
  useJarvisSocket: () => ({
    connectionStatus: 'CONNECTED',
    assistantState: 'LISTENING',
    activity: [],
    pushActivity: vi.fn(),
    registerMessageHandler: vi.fn(),
  }),
}));

function NavHarness() {
  const navigation = usePanelNavigation();
  return <PanelNavigation navigation={navigation} />;
}

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/" element={<NavHarness />} />
        <Route path="/applications" element={<NavHarness />} />
        <Route path="/system" element={<NavHarness />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('panel navigation UI', () => {
  it('selects core by default', () => {
    renderAt('/');
    expect(screen.getByRole('tab', { name: 'Core' })).toHaveAttribute(
      'aria-selected',
      'true',
    );
  });

  it('selects applications route', () => {
    renderAt('/applications');
    expect(screen.getByRole('tab', { name: 'Applications' })).toHaveAttribute(
      'aria-selected',
      'true',
    );
  });

  it('selects system route', () => {
    renderAt('/system');
    expect(screen.getByRole('tab', { name: 'System' })).toHaveAttribute(
      'aria-selected',
      'true',
    );
  });

  it('navigates with dots and respects boundaries', async () => {
    const user = userEvent.setup();
    renderAt('/');
    await user.click(screen.getByRole('tab', { name: 'System' }));
    expect(screen.getByRole('tab', { name: 'System' })).toHaveAttribute(
      'aria-selected',
      'true',
    );
    expect(screen.getByRole('button', { name: 'Next panel' })).toBeDisabled();
    await user.click(screen.getByRole('tab', { name: 'Applications' }));
    expect(screen.getByRole('button', { name: 'Previous panel' })).toBeDisabled();
  });
});

describe('Jarvis core visuals', () => {
  it('renders listening label', () => {
    render(
      <JarvisCore
        assistantState="LISTENING"
        connected
        reducedMotion
        tabVisible
        label="Listening"
      />,
    );
    expect(screen.getByRole('img', { name: /Listening/i })).toBeInTheDocument();
    expect(mapAssistantToCoreState('READY', true)).toBe('ready');
  });
});

function mockDashboard(
  partial: Partial<DashboardContextValue>,
): DashboardContextValue {
  const voice = {
    voiceStatus: null,
    loading: false,
    error: null,
    pending: false,
    activationVisible: false,
    lastWake: null,
    refresh: vi.fn(),
    start: vi.fn(),
    stop: vi.fn(),
    selectDevice: vi.fn(),
    handleSocketMessage: vi.fn(),
  };
  const speech = {
    ttsStatus: null,
    loading: false,
    error: null,
    pending: false,
    currentUtterance: null,
    sequenceCompleteVisible: false,
    initializingVisible: false,
    speaking: false,
    refresh: vi.fn(),
    testWelcome: vi.fn(),
    cancel: vi.fn(),
    retry: vi.fn(),
    selectDevice: vi.fn(),
    handleSocketMessage: vi.fn(),
  };
  const workspace = {
    workspaceStatus: null,
    applications: [],
    loading: false,
    error: null,
    pending: false,
    pendingAppIds: new Set<string>(),
    banner: null,
    isRunning: false,
    refresh: vi.fn(),
    start: vi.fn(),
    cancel: vi.fn(),
    reloadRegistry: vi.fn(),
    openApp: vi.fn(),
    focusApp: vi.fn(),
    handleSocketMessage: vi.fn(),
  };
  return {
    connectionStatus: 'CONNECTED',
    assistantState: 'LISTENING',
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
    voice: voice as DashboardContextValue['voice'],
    speech: speech as DashboardContextValue['speech'],
    workspace: workspace as DashboardContextValue['workspace'],
    ...partial,
  };
}

describe('activation sequence', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows processing and speaking labels', () => {
    const { rerender } = render(
      <DashboardContext.Provider
        value={mockDashboard({
          assistantState: 'PROCESSING',
          voice: {
            ...mockDashboard({}).voice,
            activationVisible: true,
          },
        })}
      >
        <ActivationSequence />
      </DashboardContext.Provider>,
    );
    expect(screen.getByTestId('activation-sequence')).toHaveTextContent(
      /PROCESSING AUTHORIZATION|VOICE ACTIVATION/,
    );

    rerender(
      <DashboardContext.Provider
        value={mockDashboard({
          assistantState: 'SPEAKING',
          speech: {
            ...mockDashboard({}).speech,
            speaking: true,
            currentUtterance: {
              sequence: 'welcome',
              index: 2,
              total: 3,
              text: 'All systems are online.',
            },
          },
        })}
      >
        <ActivationSequence />
      </DashboardContext.Provider>,
    );
    expect(screen.getByText('JARVIS SPEAKING')).toBeInTheDocument();
    expect(screen.getByText('2 / 3')).toBeInTheDocument();
    expect(screen.getByText('All systems are online.')).toBeInTheDocument();
  });

  it('shows workspace progress and ready', () => {
    render(
      <DashboardContext.Provider
        value={mockDashboard({
          assistantState: 'OPENING_APPLICATIONS',
          workspace: {
            ...mockDashboard({}).workspace,
            isRunning: true,
            workspaceStatus: {
              enabled: true,
              status: 'LAUNCHING',
              active_run_id: 'r1',
              profile: 'default',
              total_configured: 7,
              total_enabled: 7,
              current_application: 'vscode',
              progress: { completed: 2, total: 7 },
              last_run: null,
              last_error: null,
            },
            applications: [
              {
                applicationId: 'vscode',
                displayName: 'Visual Studio Code',
                status: 'LAUNCHING',
                running: false,
                windowFound: false,
                focusSucceeded: false,
                processId: null,
                error: null,
                result: null,
                durationMs: null,
                enabled: true,
                order: 10,
                launchType: 'executable',
                resolved: true,
              },
            ],
          },
        })}
      >
        <ActivationSequence />
      </DashboardContext.Provider>,
    );
    expect(screen.getByText('OPENING WORKSPACE')).toBeInTheDocument();
    expect(screen.getByText('2 / 7')).toBeInTheDocument();
  });
});
