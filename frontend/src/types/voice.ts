export type VoiceServiceStatus =
  | 'DISABLED'
  | 'STARTING'
  | 'LOADING_MODEL'
  | 'LISTENING'
  | 'ACTIVATION_DETECTED'
  | 'STOPPING'
  | 'STOPPED'
  | 'MODEL_MISSING'
  | 'ERROR';

export interface MicrophoneInfo {
  id: number | null;
  name: string | null;
  is_default: boolean;
}

export interface VoiceStatus {
  enabled: boolean;
  status: VoiceServiceStatus;
  wake_phrase: string;
  model_loaded: boolean;
  model_path: string;
  microphone: MicrophoneInfo | null;
  last_activation_at: string | null;
  last_error: string | null;
}

export interface AudioDevice {
  id: number;
  name: string;
  host_api: string;
  max_input_channels: number;
  default_sample_rate: number;
  is_default: boolean;
}

export interface VoiceStatusChangedPayload {
  status: VoiceServiceStatus;
  microphone_name?: string | null;
  enabled?: boolean;
  model_loaded?: boolean;
  wake_phrase?: string;
  last_error?: string | null;
  last_activation_at?: string | null;
}

export interface VoiceWakeDetectedPayload {
  phrase: string;
  confidence: number;
}

export interface VoiceErrorPayload {
  code: string;
  message: string;
}
