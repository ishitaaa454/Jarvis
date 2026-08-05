export type WorkspaceServiceStatus =
  | 'IDLE'
  | 'PREPARING'
  | 'LAUNCHING'
  | 'CANCELLING'
  | 'READY'
  | 'PARTIAL_SUCCESS'
  | 'CANCELLED'
  | 'ERROR';

export type ApplicationActionStatus =
  | 'PENDING'
  | 'CHECKING'
  | 'ALREADY_RUNNING'
  | 'RESTORING'
  | 'FOCUSING'
  | 'LAUNCHING'
  | 'OPENING_URL'
  | 'OPENING_URI'
  | 'WAITING_FOR_STARTUP'
  | 'READY'
  | 'SKIPPED'
  | 'FAILED'
  | 'CANCELLED';

export type LaunchType = 'executable' | 'url' | 'uri' | 'start_app' | 'browser_url';

export interface WorkspaceProgress {
  completed: number;
  total: number;
}

export interface ApplicationActionResult {
  application_id: string;
  display_name: string;
  requested_action: string;
  result: string;
  running: boolean;
  window_found: boolean;
  focus_requested: boolean;
  focus_succeeded: boolean;
  process_id: number | null;
  duration_ms: number;
  error: string | null;
  status: ApplicationActionStatus;
}

export interface WorkspaceRunSummary {
  run_id: string;
  status: WorkspaceServiceStatus;
  started_at: string | null;
  finished_at: string | null;
  duration_ms: number;
  total_applications: number;
  successful: number;
  failed: number;
  skipped: number;
  applications: ApplicationActionResult[];
}

export interface WorkspaceStatus {
  enabled: boolean;
  status: WorkspaceServiceStatus;
  active_run_id: string | null;
  profile: string;
  total_configured: number;
  total_enabled: number;
  current_application: string | null;
  progress: WorkspaceProgress;
  last_run: WorkspaceRunSummary | null;
  last_error: string | null;
}

export interface ApplicationRuntimeView {
  id: string;
  display_name: string;
  enabled: boolean;
  order: number;
  launch_type: LaunchType;
  resolved: boolean;
  running: boolean;
  window_found: boolean;
  status: ApplicationActionStatus;
  last_result: string | null;
}

/**
 * Flattened, camelCase view of a single application's live launch state used
 * throughout the workspace UI. Built from `ApplicationRuntimeView` (REST) and
 * kept in sync by `useWorkspaceStatus` via `workspace.*` WebSocket events.
 */
export interface ApplicationRuntimeStatus {
  applicationId: string;
  displayName: string;
  status: ApplicationActionStatus;
  running: boolean;
  windowFound: boolean;
  focusSucceeded: boolean;
  processId: number | null;
  error: string | null;
  result: string | null;
  durationMs: number | null;
  enabled: boolean;
  order: number;
  launchType: LaunchType;
  resolved: boolean;
}

// ---------------------------------------------------------------------------
// WebSocket event payloads (see backend app/models/application.py and
// app/services/workspace/workspace_service.py for the authoritative shapes)
// ---------------------------------------------------------------------------

export interface WorkspaceStatusChangedPayload {
  status: WorkspaceServiceStatus;
  active_run_id: string | null;
  profile: string;
  total_enabled: number;
  current_application: string | null;
  progress: WorkspaceProgress;
  last_error: string | null;
}

export interface WorkspaceRunStartedPayload {
  run_id: string;
  total: number;
  profile: string;
}

export interface WorkspaceApplicationStatusPayload {
  run_id: string;
  application_id: string;
  display_name: string;
  status: ApplicationActionStatus;
  [key: string]: unknown;
}

export interface WorkspaceApplicationResultPayload extends ApplicationActionResult {
  run_id: string;
}

export interface WorkspaceRunFinishedPayload {
  run_id: string;
  status: WorkspaceServiceStatus;
  summary: WorkspaceRunSummary;
}

export interface WorkspaceRunCancelledPayload {
  run_id: string;
}

export interface WorkspaceWarningPayload {
  run_id?: string;
  application_id?: string;
  message: string;
}

export interface WorkspaceErrorPayload {
  run_id?: string;
  message: string;
}

export interface AssistantWorkspaceReadyPayload {
  status: WorkspaceServiceStatus;
}
