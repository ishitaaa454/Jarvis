import { useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';

import { useDashboard } from '../../context/DashboardContext';
import type { SystemSection } from '../../types/systemMonitor';
import {
  displayAvailability,
  formatBytes,
  formatMhz,
  formatPercent,
  formatRate,
  formatUptime,
} from '../../utils/formatMetrics';
import { MetricLineChart } from '../system-monitor/MetricLineChart';
import { MetricUnavailable } from '../system-monitor/MetricUnavailable';
import styles from './SystemIntelligencePanel.module.css';

const SECTIONS: Array<{ id: SystemSection; label: string }> = [
  { id: 'overview', label: 'Overview' },
  { id: 'cpu', label: 'CPU' },
  { id: 'memory', label: 'Memory' },
  { id: 'storage', label: 'Storage' },
  { id: 'network', label: 'Network' },
  { id: 'power', label: 'Power' },
  { id: 'gpu', label: 'GPU' },
  { id: 'temperatures', label: 'Temperatures' },
  { id: 'processes', label: 'Processes' },
  { id: 'capabilities', label: 'Capabilities' },
];

function isSection(value: string | null): value is SystemSection {
  return SECTIONS.some((section) => section.id === value);
}

export function SystemIntelligencePanel() {
  const { systemMonitor, reducedMotion, connectionStatus, dataStale } = useDashboard();
  const [params, setParams] = useSearchParams();
  const requested = params.get('section');
  const [section, setSection] = useState<SystemSection>(
    isSection(requested) ? requested : 'overview',
  );
  const [processSearch, setProcessSearch] = useState('');
  const [processSort, setProcessSort] = useState('cpu');
  const [processLimit, setProcessLimit] = useState(20);

  useEffect(() => {
    if (isSection(requested)) setSection(requested);
  }, [requested]);

  useEffect(() => {
    if (section === 'processes') {
      void systemMonitor.refreshProcesses({
        sort: processSort,
        limit: processLimit,
        search: processSearch,
      });
    }
  }, [section, processSort, processLimit, processSearch, systemMonitor.refreshProcesses]);

  const snap = systemMonitor.snapshot;
  const series = systemMonitor.series;
  const freshness = systemMonitor.freshness;

  const selectSection = (id: SystemSection) => {
    setSection(id);
    setParams(id === 'overview' ? {} : { section: id }, { replace: true });
  };

  const processRows = useMemo(() => systemMonitor.processes?.processes ?? [], [systemMonitor.processes]);

  return (
    <div className={styles.root} data-testid="system-panel">
      <header className={styles.header}>
        <div>
          <h2>System Intelligence</h2>
          <p>
            Local monitoring · {systemMonitor.status?.status ?? 'UNKNOWN'} · {freshness}
            {dataStale || connectionStatus !== 'CONNECTED' ? ' · STALE CONNECTION' : ''}
          </p>
        </div>
        <button
          type="button"
          className={styles.refresh}
          data-no-swipe
          onClick={() => void systemMonitor.requestRefresh()}
        >
          Refresh
        </button>
      </header>

      <nav className={styles.tabs} aria-label="System sections">
        {SECTIONS.map((item) => (
          <button
            key={item.id}
            type="button"
            className={section === item.id ? styles.tabActive : styles.tab}
            aria-current={section === item.id ? 'page' : undefined}
            onClick={() => selectSection(item.id)}
            data-no-swipe
          >
            {item.label}
          </button>
        ))}
      </nav>

      {systemMonitor.error ? <p className={styles.error}>{systemMonitor.error}</p> : null}

      {section === 'overview' && (
        <div className={styles.grid}>
          <MetricCard
            title="CPU"
            value={formatPercent(snap?.cpu.usage_percent)}
            points={series['cpu.usage_percent'] ?? []}
            reducedMotion={reducedMotion}
            onOpen={() => selectSection('cpu')}
          />
          <MetricCard
            title="Memory"
            value={formatPercent(snap?.memory.usage_percent)}
            points={series['memory.usage_percent'] ?? []}
            reducedMotion={reducedMotion}
            onOpen={() => selectSection('memory')}
          />
          <MetricCard
            title="Disk read"
            value={formatRate(snap?.disks.activity.read_bytes_per_second)}
            points={series['disk.read_bytes_per_second'] ?? []}
            reducedMotion={reducedMotion}
            onOpen={() => selectSection('storage')}
          />
          <MetricCard
            title="Network receive"
            value={formatRate(snap?.network.receive_bytes_per_second)}
            points={series['network.receive_bytes_per_second'] ?? []}
            reducedMotion={reducedMotion}
            onOpen={() => selectSection('network')}
          />
          <MetricCard
            title="Battery"
            value={
              snap?.battery.present
                ? formatPercent(snap.battery.percent)
                : 'NO BATTERY DETECTED'
            }
            points={series['battery.percent'] ?? []}
            reducedMotion={reducedMotion}
            onOpen={() => selectSection('power')}
          />
          <MetricCard
            title="GPU"
            value={
              snap?.gpu.availability === 'AVAILABLE'
                ? formatPercent(snap.gpu.devices[0]?.usage_percent)
                : displayAvailability(snap?.gpu.availability)
            }
            points={series['gpu.usage_percent'] ?? []}
            reducedMotion={reducedMotion}
            onOpen={() => selectSection('gpu')}
          />
          <div className={styles.infoCard}>
            <h3>Uptime</h3>
            <p>{formatUptime(snap?.static.uptime_seconds)}</p>
          </div>
        </div>
      )}

      {section === 'cpu' && (
        <div className={styles.section}>
          <div className={styles.grid}>
            <div className={styles.infoCard}>
              <h3>Overall</h3>
              <p>{formatPercent(snap?.cpu.usage_percent)}</p>
              <MetricLineChart
                label="CPU"
                points={series['cpu.usage_percent'] ?? []}
                unit="%"
                reducedMotion={reducedMotion}
              />
            </div>
            <div className={styles.infoCard}>
              <h3>Frequency</h3>
              <p>{formatMhz(snap?.cpu.frequency_mhz)}</p>
              <p className={styles.muted}>
                Cores {snap?.cpu.physical_cores ?? '—'} physical /{' '}
                {snap?.cpu.logical_cores ?? '—'} logical
              </p>
              <p className={styles.muted}>{snap?.cpu.architecture ?? 'UNKNOWN'}</p>
            </div>
          </div>
          <div className={styles.coreGrid}>
            {(snap?.cpu.per_core_percent ?? []).map((value, index) => (
              <div key={index} className={styles.coreCell}>
                <span>Core {index}</span>
                <strong>{formatPercent(value, 0)}</strong>
              </div>
            ))}
          </div>
        </div>
      )}

      {section === 'memory' && (
        <div className={styles.section}>
          <div className={styles.grid}>
            <div className={styles.infoCard}>
              <h3>Physical memory</h3>
              <p>{formatPercent(snap?.memory.usage_percent)}</p>
              <p className={styles.muted}>
                Used {formatBytes(snap?.memory.used_bytes)} · Available{' '}
                {formatBytes(snap?.memory.available_bytes)} · Total{' '}
                {formatBytes(snap?.memory.total_bytes)}
              </p>
              <MetricLineChart
                label="Memory"
                points={series['memory.usage_percent'] ?? []}
                unit="%"
                reducedMotion={reducedMotion}
              />
            </div>
            <div className={styles.infoCard}>
              <h3>Swap</h3>
              <p>
                {snap?.memory.swap_availability === 'AVAILABLE'
                  ? formatPercent(snap.memory.swap_percent)
                  : displayAvailability(snap?.memory.swap_availability)}
              </p>
              <p className={styles.muted}>
                Used {formatBytes(snap?.memory.swap_used_bytes)} · Total{' '}
                {formatBytes(snap?.memory.swap_total_bytes)}
              </p>
            </div>
          </div>
        </div>
      )}

      {section === 'storage' && (
        <div className={styles.section}>
          <div className={styles.infoCard}>
            <h3>Aggregate disk activity</h3>
            <p>
              Read {formatRate(snap?.disks.activity.read_bytes_per_second)} · Write{' '}
              {formatRate(snap?.disks.activity.write_bytes_per_second)}
            </p>
            <MetricLineChart
              label="Disk read"
              points={series['disk.read_bytes_per_second'] ?? []}
              reducedMotion={reducedMotion}
            />
          </div>
          <div className={styles.grid}>
            {(snap?.disks.drives ?? []).map((drive) => (
              <div key={drive.mountpoint} className={styles.infoCard}>
                <h3>{drive.mountpoint}</h3>
                <p>{formatPercent(drive.usage_percent)}</p>
                <p className={styles.muted}>
                  {drive.fstype ?? 'unknown'} · Used {formatBytes(drive.used_bytes)} · Free{' '}
                  {formatBytes(drive.free_bytes)} · Total {formatBytes(drive.total_bytes)}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {section === 'network' && (
        <div className={styles.section}>
          <div className={styles.grid}>
            <div className={styles.infoCard}>
              <h3>Network receive</h3>
              <p>{formatRate(snap?.network.receive_bytes_per_second)}</p>
              <MetricLineChart
                label="Receive"
                points={series['network.receive_bytes_per_second'] ?? []}
                reducedMotion={reducedMotion}
              />
            </div>
            <div className={styles.infoCard}>
              <h3>Network send</h3>
              <p>{formatRate(snap?.network.send_bytes_per_second)}</p>
              <MetricLineChart
                label="Send"
                points={series['network.send_bytes_per_second'] ?? []}
                reducedMotion={reducedMotion}
              />
            </div>
          </div>
          <div className={styles.tableWrap}>
            <table>
              <thead>
                <tr>
                  <th scope="col">Adapter</th>
                  <th scope="col">Status</th>
                  <th scope="col">Link</th>
                  <th scope="col">MTU</th>
                </tr>
              </thead>
              <tbody>
                {(snap?.network.adapters ?? []).map((adapter) => (
                  <tr key={adapter.name}>
                    <td>{adapter.name}</td>
                    <td>{adapter.is_up ? 'Up' : 'Down'}</td>
                    <td>
                      {adapter.speed_mbps != null ? `${adapter.speed_mbps} Mbps` : 'UNAVAILABLE'}
                    </td>
                    <td>{adapter.mtu ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {section === 'power' && (
        <div className={styles.section}>
          {snap?.battery.present ? (
            <div className={styles.infoCard}>
              <h3>Battery</h3>
              <p>{formatPercent(snap.battery.percent)}</p>
              <p className={styles.muted}>
                {snap.battery.status.replaceAll('_', ' ')}
                {snap.battery.power_plugged ? ' · AC connected' : ''}
              </p>
              <p className={styles.muted}>
                Remaining:{' '}
                {snap.battery.secsleft_unknown || snap.battery.secsleft == null
                  ? 'UNKNOWN'
                  : formatUptime(snap.battery.secsleft)}
              </p>
              <MetricLineChart
                label="Battery"
                points={series['battery.percent'] ?? []}
                unit="%"
                reducedMotion={reducedMotion}
              />
            </div>
          ) : (
            <MetricUnavailable
              title="NO BATTERY DETECTED"
              reason="Normal for desktop systems without a battery."
            />
          )}
        </div>
      )}

      {section === 'gpu' && (
        <div className={styles.section}>
          {snap?.gpu.availability === 'AVAILABLE' && snap.gpu.devices.length > 0 ? (
            snap.gpu.devices.map((gpu) => (
              <div key={gpu.index} className={styles.infoCard}>
                <h3>{gpu.name}</h3>
                <p>Usage {formatPercent(gpu.usage_percent)}</p>
                <p className={styles.muted}>
                  Memory {formatBytes(gpu.memory_used_bytes)} /{' '}
                  {formatBytes(gpu.memory_total_bytes)} (
                  {formatPercent(gpu.memory_percent)})
                </p>
                <p className={styles.muted}>
                  Temp {gpu.temperature_celsius != null ? `${gpu.temperature_celsius}°C` : 'UNAVAILABLE'}{' '}
                  · Power {gpu.power_watts != null ? `${gpu.power_watts} W` : 'UNAVAILABLE'} · Fan{' '}
                  {formatPercent(gpu.fan_speed_percent)}
                </p>
              </div>
            ))
          ) : (
            <MetricUnavailable
              title="GPU MONITORING UNAVAILABLE"
              reason={snap?.gpu.reason ?? displayAvailability(snap?.gpu.availability)}
              onRetry={() => void systemMonitor.retryProvider('gpu')}
            />
          )}
        </div>
      )}

      {section === 'temperatures' && (
        <div className={styles.section}>
          {snap?.temperatures.availability === 'AVAILABLE' &&
          snap.temperatures.readings.length > 0 ? (
            <div className={styles.grid}>
              {snap.temperatures.readings.map((reading) => (
                <div key={`${reading.category}-${reading.name}`} className={styles.infoCard}>
                  <h3>
                    {reading.category} · {reading.name}
                  </h3>
                  <p>{reading.celsius.toFixed(1)}°C</p>
                  <p className={styles.muted}>
                    Critical{' '}
                    {reading.critical_celsius != null
                      ? `${reading.critical_celsius}°C`
                      : 'UNAVAILABLE'}{' '}
                    · {reading.provider}
                  </p>
                </div>
              ))}
            </div>
          ) : (
            <MetricUnavailable
              title="TEMPERATURE PROVIDER NOT AVAILABLE"
              reason={
                snap?.temperatures.reason ??
                displayAvailability(snap?.temperatures.availability)
              }
              onRetry={() => void systemMonitor.retryProvider('temperatures')}
            />
          )}
        </div>
      )}

      {section === 'processes' && (
        <div className={styles.section}>
          <div className={styles.processControls}>
            <label>
              Search
              <input
                value={processSearch}
                onChange={(event) => setProcessSearch(event.target.value)}
                data-no-swipe
              />
            </label>
            <label>
              Sort
              <select
                value={processSort}
                onChange={(event) => setProcessSort(event.target.value)}
                data-no-swipe
              >
                <option value="cpu">CPU</option>
                <option value="memory">Memory</option>
                <option value="name">Name</option>
                <option value="pid">PID</option>
              </select>
            </label>
            <label>
              Limit
              <select
                value={processLimit}
                onChange={(event) => setProcessLimit(Number(event.target.value))}
                data-no-swipe
              >
                {[15, 20, 25, 50].map((n) => (
                  <option key={n} value={n}>
                    {n}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <p className={styles.muted}>
            Limited inspections: {systemMonitor.processes?.limited_count ?? 0} · Read-only
          </p>
          <div className={styles.tableWrap}>
            <table>
              <thead>
                <tr>
                  <th scope="col">Process</th>
                  <th scope="col">PID</th>
                  <th scope="col">CPU</th>
                  <th scope="col">Memory</th>
                  <th scope="col">RSS</th>
                  <th scope="col">Status</th>
                </tr>
              </thead>
              <tbody>
                {processRows.map((proc) => (
                  <tr key={`${proc.pid}-${proc.create_time ?? 0}`}>
                    <td>{proc.name}</td>
                    <td>{proc.pid}</td>
                    <td>{formatPercent(proc.cpu_percent)}</td>
                    <td>{formatPercent(proc.memory_percent)}</td>
                    <td>{formatBytes(proc.memory_rss_bytes)}</td>
                    <td>{proc.status ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {section === 'capabilities' && (
        <div className={styles.section}>
          <div className={styles.tableWrap}>
            <table>
              <tbody>
                {Object.entries(systemMonitor.capabilities ?? {}).map(([key, value]) => (
                  <tr key={key}>
                    <th scope="row">{key}</th>
                    <td>
                      {value.available ? 'Available' : 'Unavailable'}
                      {value.limited ? ' (limited)' : ''}
                      {value.provider ? ` · ${value.provider}` : ''}
                      {value.reason ? ` — ${value.reason}` : ''}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

function MetricCard({
  title,
  value,
  points,
  reducedMotion,
  onOpen,
}: {
  title: string;
  value: string;
  points: Array<{ timestamp: number; value: number | null }>;
  reducedMotion: boolean;
  onOpen: () => void;
}) {
  return (
    <button type="button" className={styles.metricCard} onClick={onOpen} data-no-swipe>
      <h3>{title}</h3>
      <p>{value}</p>
      <MetricLineChart label={title} points={points} reducedMotion={reducedMotion} />
    </button>
  );
}
