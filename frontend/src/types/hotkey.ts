export interface HotkeyShortcut {
  action: string;
  display: string;
}

export interface HotkeyStatus {
  enabled: boolean;
  status: string;
  shortcuts: HotkeyShortcut[];
  last_triggered_at: string | null;
  conflict_message: string | null;
}
