/** Phase 7 window / command-centre types. */

export interface SafeWindowRecord {
  window_id: string;
  application_id: string;
  process_id: number | null;
  display_title: string;
  visible: boolean;
  minimized: boolean;
  foreground: boolean;
  focusable: boolean;
  first_seen_at: string | null;
  last_seen_at: string | null;
  last_jarvis_focus_at: string | null;
}

export interface ApplicationWindowGroup {
  application_id: string;
  display_name: string;
  running: boolean;
  window_count: number;
  foreground: boolean;
  favourite: boolean;
  allow_preview: boolean;
  windows: SafeWindowRecord[];
}

export interface WindowInventorySnapshot {
  applications: ApplicationWindowGroup[];
  total_windows: number;
  running_applications: number;
  foreground_application_id: string | null;
  foreground_window_id: string | null;
  collected_at: string | null;
  available: boolean;
  reason: string | null;
}

export interface RecentWindowRecord {
  window_id: string;
  application_id: string;
  display_name: string;
  display_title: string;
  last_foreground_at: string;
}

export interface WindowFocusResult {
  application_id: string;
  window_id: string;
  result: string;
  restored: boolean;
  foreground: boolean;
  focus_limited: boolean;
  error: string | null;
}
