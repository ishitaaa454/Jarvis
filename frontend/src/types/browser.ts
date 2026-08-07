export interface BrowserDestination {
  id: string;
  display_name: string;
  known_open: boolean;
  exact_focus_available: boolean;
  url: string | null;
  last_opened_at: string | null;
  last_focused_at: string | null;
}

export interface BrowserStatus {
  enabled: boolean;
  status: string;
  mode: string;
  cdp_enabled: boolean;
  exact_tab_focus_available: boolean;
  reason: string | null;
}
