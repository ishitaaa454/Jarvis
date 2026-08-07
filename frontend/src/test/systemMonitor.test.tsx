import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';

import { MetricLineChart } from '../components/system-monitor/MetricLineChart';
import { MetricUnavailable } from '../components/system-monitor/MetricUnavailable';
import { SystemIntelligencePanel } from '../components/system/SystemIntelligencePanel';
import type { DashboardContextValue } from '../context/DashboardContext';
import { DashboardContext } from '../context/DashboardContext';
import { computeFreshness } from '../hooks/useSystemMonitor';
import { createMetricHistory } from '../reducers/metricHistoryReducer';
import type { SystemMonitorSnapshot } from '../types/systemMonitor';
import {
  displayAvailability,
  formatBytes,
  formatPercent,
  formatRate,
} from '../utils/formatMetrics';

function baseSnapshot(partial: Partial<SystemMonitorSnapshot> = {}): SystemMonitorSnapshot {
  return {
    timestamp: new Date().toISOString(),
    cpu: {
      usage_percent: 24.7,
      per_core_percent: [10, 20, 30, 40],
      physical_cores: 4,
      logical_cores: 4,
      frequency_mhz: 2800,
      frequency_min_mhz: null,
      frequency_max_mhz: 4200,
      architecture: 'AMD64',
      collected_at: new Date().toISOString(),
      availability: 'AVAILABLE',
    },
    memory: {
      total_bytes: 16 * 1024 ** 3,
      used_bytes: 8 * 1024 ** 3,
      available_bytes: 8 * 1024 ** 3,
      usage_percent: 50,
      swap_total_bytes: 4 * 1024 ** 3,
      swap_used_bytes: 1 * 1024 ** 3,
      swap_free_bytes: 3 * 1024 ** 3,
      swap_percent: 25,
      collected_at: new Date().toISOString(),
      availability: 'AVAILABLE',
      swap_availability: 'AVAILABLE',
    },
    disks: {
      drives: [
        {
          device: 'C:',
          mountpoint: 'C:\\',
          fstype: 'NTFS',
          total_bytes: 500 * 1024 ** 3,
          used_bytes: 200 * 1024 ** 3,
          free_bytes: 300 * 1024 ** 3,
          usage_percent: 40,
          read_only: false,
        },
      ],
      activity: {
        read_bytes_per_second: 1_800_000,
        write_bytes_per_second: 420_000,
        read_ops_per_second: 12,
        write_ops_per_second: 4,
        busy_percent: null,
        collected_at: new Date().toISOString(),
        availability: 'AVAILABLE',
      },
      collected_at: new Date().toISOString(),
      availability: 'AVAILABLE',
    },
    network: {
      receive_bytes_per_second: 3_200_000,
      send_bytes_per_second: 180_000,
      bytes_recv_total: 1e9,
      bytes_sent_total: 2e8,
      adapters: [
        {
          name: 'Ethernet',
          is_up: true,
          speed_mbps: 1000,
          mtu: 1500,
          ipv4: null,
          has_ipv6: true,
          bytes_recv: 1e9,
          bytes_sent: 2e8,
        },
      ],
      active_adapter_count: 1,
      collected_at: new Date().toISOString(),
      availability: 'AVAILABLE',
    },
    battery: {
      present: false,
      percent: null,
      status: 'NOT_PRESENT',
      power_plugged: true,
      secsleft: null,
      secsleft_unknown: true,
      collected_at: new Date().toISOString(),
      availability: 'NOT_DETECTED',
    },
    static: {
      os_name: 'Windows',
      os_release: '10',
      os_version: '10.0',
      architecture: 'AMD64',
      hostname: 'TEST-PC',
      python_version: '3.11',
      backend_version: '0.1.0',
      boot_time: null,
      uptime_seconds: 3600,
      physical_cores: 4,
      logical_cores: 4,
      collected_at: new Date().toISOString(),
    },
    gpu: {
      devices: [],
      provider: null,
      collected_at: null,
      availability: 'PROVIDER_NOT_INSTALLED',
      reason: 'NVML provider is not installed',
    },
    temperatures: {
      readings: [],
      provider: null,
      collected_at: null,
      availability: 'UNSUPPORTED',
      reason: 'No supported temperature provider',
    },
    status: 'RUNNING',
    degraded: true,
    capabilities: null,
    ...partial,
  };
}

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
    voice: {
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
    } as DashboardContextValue['voice'],
    speech: {
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
    } as DashboardContextValue['speech'],
    workspace: {
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
    } as DashboardContextValue['workspace'],
    systemMonitor: {
      status: {
        enabled: true,
        status: 'DEGRADED',
        started_at: null,
        last_fast_sample_at: null,
        last_process_sample_at: null,
        last_static_refresh_at: null,
        history_samples: 10,
        degraded: true,
        provider_errors: [],
      },
      snapshot: baseSnapshot(),
      capabilities: {
        cpu: { available: true, provider: 'psutil' },
        memory: { available: true, provider: 'psutil' },
        disk: { available: true, provider: 'psutil' },
        network: { available: true, provider: 'psutil' },
        battery: { available: false, reason: 'No battery detected', code: 'NOT_DETECTED' },
        gpu: {
          available: false,
          reason: 'NVML provider is not installed',
          code: 'PROVIDER_NOT_INSTALLED',
        },
        temperatures: {
          available: false,
          reason: 'No supported temperature provider',
          code: 'UNSUPPORTED',
        },
        processes: {
          available: true,
          limited: true,
          reason: 'Some protected processes cannot be inspected',
        },
      },
      processes: {
        processes: [
          {
            pid: 1,
            name: 'System',
            cpu_percent: 1.2,
            memory_percent: 0.1,
            memory_rss_bytes: 1024,
            status: 'running',
            create_time: 1,
          },
        ],
        total_observed: 1,
        returned: 1,
        limited_count: 2,
        collected_at: new Date().toISOString(),
        availability: 'AVAILABLE',
      },
      series: {
        'cpu.usage_percent': [
          { timestamp: Date.now() - 1000, value: 20 },
          { timestamp: Date.now(), value: 24.7 },
        ],
      },
      freshness: 'LIVE',
      error: null,
      loading: false,
      refresh: vi.fn(),
      refreshProcesses: vi.fn(),
      retryProvider: vi.fn(),
      requestRefresh: vi.fn(),
      handleSocketMessage: vi.fn(),
    } as DashboardContextValue['systemMonitor'],
    ...partial,
  };
}

function renderSystem(path = '/system') {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <DashboardContext.Provider value={mockDashboard()}>
        <Routes>
          <Route path="/system" element={<SystemIntelligencePanel />} />
        </Routes>
      </DashboardContext.Provider>
    </MemoryRouter>,
  );
}

describe('formatMetrics', () => {
  it('formats binary bytes and rates', () => {
    expect(formatBytes(1024)).toBe('1.0 KiB');
    expect(formatRate(1024)).toBe('1.0 KiB/s');
    expect(formatPercent(null)).toBe('UNAVAILABLE');
    expect(formatPercent(12.34)).toBe('12.3%');
    expect(displayAvailability('PROVIDER_NOT_INSTALLED')).toBe('PROVIDER NOT INSTALLED');
  });
});

describe('MetricLineChart', () => {
  it('handles empty history', () => {
    const { container } = render(<MetricLineChart label="CPU" points={[]} />);
    expect(container.querySelector('svg[aria-label="CPU: no samples"]')).toBeTruthy();
  });

  it('handles one sample and constant values', () => {
    render(
      <MetricLineChart
        label="CPU"
        points={[
          { timestamp: 1, value: 10 },
          { timestamp: 2, value: 10 },
        ]}
        unit="%"
      />,
    );
    expect(screen.getByRole('img', { name: /constant 10.0%/i })).toBeInTheDocument();
  });

  it('handles missing samples without inventing values', () => {
    render(
      <MetricLineChart
        label="CPU"
        points={[
          { timestamp: 1, value: 10 },
          { timestamp: 2, value: null },
          { timestamp: 3, value: 20 },
        ]}
        unit="%"
      />,
    );
    expect(screen.getByRole('img', { name: /range 10.0–20.0%/i })).toBeInTheDocument();
  });
});

describe('MetricUnavailable', () => {
  it('shows reason and optional retry', async () => {
    const onRetry = vi.fn();
    const user = userEvent.setup();
    render(
      <MetricUnavailable title="GPU MONITORING UNAVAILABLE" reason="Provider missing" onRetry={onRetry} />,
    );
    expect(screen.getByText('GPU MONITORING UNAVAILABLE')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /retry/i }));
    expect(onRetry).toHaveBeenCalled();
  });
});

describe('SystemIntelligencePanel', () => {
  it('shows overview with real snapshot values and no fake zeros for unsupported GPU', () => {
    renderSystem('/system');
    expect(screen.getByText('24.7%')).toBeInTheDocument();
    expect(screen.getByText('NO BATTERY DETECTED')).toBeInTheDocument();
    expect(screen.getByText(/PROVIDER NOT INSTALLED/i)).toBeInTheDocument();
  });

  it('renders per-core grid and frequency', async () => {
    const user = userEvent.setup();
    renderSystem('/system?section=cpu');
    expect(screen.getByText('Core 0')).toBeInTheDocument();
    expect(screen.getByText('2800 MHz')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Memory' }));
    expect(screen.getByText(/Physical memory/i)).toBeInTheDocument();
  });

  it('shows disk capacity and aggregate activity label', () => {
    renderSystem('/system?section=storage');
    expect(screen.getByText('C:\\')).toBeInTheDocument();
    expect(screen.getByText(/Aggregate disk activity/i)).toBeInTheDocument();
  });

  it('shows network adapters without MAC addresses', () => {
    renderSystem('/system?section=network');
    expect(screen.getByText('Ethernet')).toBeInTheDocument();
    expect(screen.queryByText(/mac/i)).not.toBeInTheDocument();
  });

  it('shows no-battery state on power section', () => {
    renderSystem('/system?section=power');
    expect(screen.getByText('NO BATTERY DETECTED')).toBeInTheDocument();
  });

  it('shows GPU provider missing state', () => {
    renderSystem('/system?section=gpu');
    expect(screen.getByText('GPU MONITORING UNAVAILABLE')).toBeInTheDocument();
  });

  it('shows temperature unavailable state', () => {
    renderSystem('/system?section=temperatures');
    expect(screen.getByText('TEMPERATURE PROVIDER NOT AVAILABLE')).toBeInTheDocument();
  });

  it('renders safe process fields only', () => {
    renderSystem('/system?section=processes');
    expect(screen.getByText('System')).toBeInTheDocument();
    expect(screen.getByText('1')).toBeInTheDocument();
    expect(screen.queryByText(/cmdline/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/username/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/exe path/i)).not.toBeInTheDocument();
  });

  it('shows capability reasons', () => {
    renderSystem('/system?section=capabilities');
    expect(screen.getByText(/NVML provider is not installed/i)).toBeInTheDocument();
  });

  it('shows degraded monitoring status', () => {
    renderSystem('/system');
    expect(screen.getByText(/DEGRADED/i)).toBeInTheDocument();
  });
});

describe('freshness', () => {
  it('marks disconnected as STALE', () => {
    expect(computeFreshness(new Date().toISOString(), false)).toBe('STALE');
  });

  it('marks recent samples LIVE', () => {
    expect(computeFreshness(new Date().toISOString(), true, 1)).toBe('LIVE');
  });
});
