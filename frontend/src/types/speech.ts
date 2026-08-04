export type TtsServiceStatus =
  | 'DISABLED'
  | 'STARTING'
  | 'VALIDATING'
  | 'READY'
  | 'SYNTHESIZING'
  | 'SPEAKING'
  | 'CANCELLING'
  | 'STOPPED'
  | 'MODEL_MISSING'
  | 'ENGINE_MISSING'
  | 'OUTPUT_UNAVAILABLE'
  | 'ERROR';

export interface OutputDeviceInfo {
  id: number;
  name: string;
  host_api: string;
  max_output_channels: number;
  default_sample_rate: number;
  is_default: boolean;
}

export interface TtsStatus {
  enabled: boolean;
  status: TtsServiceStatus;
  engine: string;
  voice: string;
  model_loaded: boolean;
  output_device: {
    id: number | null;
    name: string | null;
    is_default: boolean;
  } | null;
  is_speaking: boolean;
  current_sequence: string | null;
  current_utterance_index: number | null;
  last_spoken_at: string | null;
  last_error: string | null;
  volume?: number | null;
  length_scale?: number | null;
  sentence_pause_ms?: number | null;
  microphone_suppressed?: boolean;
}

export interface UtteranceProgress {
  sequence: string;
  index: number;
  total: number;
  text?: string;
}
