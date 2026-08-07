/** Phase 6 system monitoring types (binary units: KiB/MiB/GiB). */

export type MonitorServiceStatus =
  | 'DISABLED'
  | 'STARTING'
  | 'RUNNING'
  | 'DEGRADED'
  | 'STOPPING'
  | 'STOPPED'
  | 'ERROR';

export type AvailabilityReason =
  | 'AVAILABLE'
  | 'UNSUPPORTED'
  | 'UNAVAILABLE'
  | 'PERMISSION_LIMITED'
  | 'NOT_DETECTED'
  | 'PROVIDER_NOT_INSTALLED'
  | 'DATA_PENDING';

export type Freshness = 'LIVE' | 'DELAYED' | 'STALE' | 'UNAVAILABLE';

export type SystemSection =
  | 'overview'
  | 'cpu'
  | 'memory'
  | 'storage'
  | 'network'
  | 'power'
  | 'gpu'
  | 'temperatures'
  | 'processes'
  | 'capabilities';

export interface CapabilityStatus {
  available: boolean;
  provider?: string | null;
  limited?: boolean;
  reason?: string | null;
  code?: AvailabilityReason | null;
}

export interface CapabilityReport {
  cpu: CapabilityStatus;
  memory: CapabilityStatus;
  disk: CapabilityStatus;
  network: CapabilityStatus;
  battery: CapabilityStatus;
  gpu: CapabilityStatus;
  temperatures: CapabilityStatus;
  processes: CapabilityStatus;
}

export interface CpuMetrics {
  usage_percent: number | null;
  per_core_percent: number[] | null;
  physical_cores: number | null;
  logical_cores: number | null;
  frequency_mhz: number | null;
  frequency_min_mhz: number | null;
  frequency_max_mhz: number | null;
  architecture: string | null;
  collected_at: string | null;
  availability: AvailabilityReason;
}

export interface MemoryMetrics {
  total_bytes: number | null;
  used_bytes: number | null;
  available_bytes: number | null;
  usage_percent: number | null;
  swap_total_bytes: number | null;
  swap_used_bytes: number | null;
  swap_free_bytes: number | null;
  swap_percent: number | null;
  collected_at: string | null;
  availability: AvailabilityReason;
  swap_availability: AvailabilityReason;
}

export interface DiskDriveMetrics {
  device: string;
  mountpoint: string;
  fstype: string | null;
  total_bytes: number | null;
  used_bytes: number | null;
  free_bytes: number | null;
  usage_percent: number | null;
  read_only: boolean | null;
}

export interface DiskActivityMetrics {
  read_bytes_per_second: number | null;
  write_bytes_per_second: number | null;
  read_ops_per_second: number | null;
  write_ops_per_second: number | null;
  busy_percent: number | null;
  collected_at: string | null;
  availability: AvailabilityReason;
}

export interface DiskMetrics {
  drives: DiskDriveMetrics[];
  activity: DiskActivityMetrics;
  collected_at: string | null;
  availability: AvailabilityReason;
}

export interface NetworkAdapterMetrics {
  name: string;
  is_up: boolean | null;
  speed_mbps: number | null;
  mtu: number | null;
  ipv4: string | null;
  has_ipv6: boolean | null;
  bytes_recv: number | null;
  bytes_sent: number | null;
}

export interface NetworkMetrics {
  receive_bytes_per_second: number | null;
  send_bytes_per_second: number | null;
  bytes_recv_total: number | null;
  bytes_sent_total: number | null;
  adapters: NetworkAdapterMetrics[];
  active_adapter_count: number;
  collected_at: string | null;
  availability: AvailabilityReason;
}

export type BatteryStatus =
  | 'CHARGING'
  | 'DISCHARGING'
  | 'FULL'
  | 'PLUGGED_IN'
  | 'UNKNOWN'
  | 'NOT_PRESENT';

export interface BatteryMetrics {
  present: boolean;
  percent: number | null;
  status: BatteryStatus;
  power_plugged: boolean | null;
  secsleft: number | null;
  secsleft_unknown: boolean;
  collected_at: string | null;
  availability: AvailabilityReason;
}

export interface StaticSystemInfo {
  os_name: string | null;
  os_release: string | null;
  os_version: string | null;
  architecture: string | null;
  hostname: string | null;
  python_version: string | null;
  backend_version: string | null;
  boot_time: string | null;
  uptime_seconds: number | null;
  physical_cores: number | null;
  logical_cores: number | null;
  collected_at: string | null;
}

export interface GpuDeviceMetrics {
  index: number;
  name: string;
  usage_percent: number | null;
  memory_used_bytes: number | null;
  memory_total_bytes: number | null;
  memory_percent: number | null;
  temperature_celsius: number | null;
  power_watts: number | null;
  fan_speed_percent: number | null;
}

export interface GpuMetrics {
  devices: GpuDeviceMetrics[];
  provider: string | null;
  collected_at: string | null;
  availability: AvailabilityReason;
  reason: string | null;
}

export interface TemperatureReading {
  category: string;
  name: string;
  celsius: number;
  critical_celsius: number | null;
  provider: string;
  collected_at: string | null;
}

export interface TemperatureMetrics {
  readings: TemperatureReading[];
  provider: string | null;
  collected_at: string | null;
  availability: AvailabilityReason;
  reason: string | null;
}

export interface ProcessRecord {
  pid: number;
  name: string;
  cpu_percent: number | null;
  memory_percent: number | null;
  memory_rss_bytes: number | null;
  status: string | null;
  create_time: number | null;
}

export interface ProcessSnapshot {
  processes: ProcessRecord[];
  total_observed: number;
  returned: number;
  limited_count: number;
  collected_at: string | null;
  availability: AvailabilityReason;
}

export interface SystemMonitorSnapshot {
  timestamp: string;
  cpu: CpuMetrics;
  memory: MemoryMetrics;
  disks: DiskMetrics;
  network: NetworkMetrics;
  battery: BatteryMetrics;
  static: StaticSystemInfo;
  gpu: GpuMetrics;
  temperatures: TemperatureMetrics;
  status: MonitorServiceStatus;
  degraded: boolean;
  capabilities: CapabilityReport | null;
}

export interface SystemMonitorStatus {
  enabled: boolean;
  status: MonitorServiceStatus;
  started_at: string | null;
  last_fast_sample_at: string | null;
  last_process_sample_at: string | null;
  last_static_refresh_at: string | null;
  history_samples: number;
  degraded: boolean;
  provider_errors: Array<{ provider: string; code: string; message: string }>;
}

export interface HistoryPoint {
  timestamp: number;
  value: number | null;
}

export const BINARY_UNITS = true; // KiB / MiB / GiB
