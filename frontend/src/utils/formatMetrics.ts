/** Binary unit formatting (1024-based) for Phase 6 metrics. */

export function formatBytes(bytes: number | null | undefined, digits = 1): string {
  if (bytes == null || !Number.isFinite(bytes)) return 'UNAVAILABLE';
  const units = ['B', 'KiB', 'MiB', 'GiB', 'TiB'];
  let value = Math.max(0, bytes);
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${value.toFixed(unit === 0 ? 0 : digits)} ${units[unit]}`;
}

export function formatRate(bytesPerSecond: number | null | undefined, digits = 1): string {
  if (bytesPerSecond == null || !Number.isFinite(bytesPerSecond)) return 'UNAVAILABLE';
  return `${formatBytes(bytesPerSecond, digits)}/s`;
}

export function formatPercent(value: number | null | undefined, digits = 1): string {
  if (value == null || !Number.isFinite(value)) return 'UNAVAILABLE';
  return `${value.toFixed(digits)}%`;
}

export function formatMhz(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return 'UNAVAILABLE';
  return `${Math.round(value)} MHz`;
}

export function formatUptime(seconds: number | null | undefined): string {
  if (seconds == null || !Number.isFinite(seconds)) return 'UNAVAILABLE';
  const total = Math.max(0, Math.floor(seconds));
  const days = Math.floor(total / 86400);
  const hours = Math.floor((total % 86400) / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  if (days > 0) return `${days}d ${hours}h ${minutes}m`;
  if (hours > 0) return `${hours}h ${minutes}m`;
  return `${minutes}m`;
}

export function displayAvailability(code: string | null | undefined, fallback = 'UNAVAILABLE'): string {
  if (!code) return fallback;
  return code.replaceAll('_', ' ');
}
