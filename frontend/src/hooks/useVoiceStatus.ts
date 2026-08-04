import { useCallback, useEffect, useRef, useState } from 'react';

import {
  fetchVoiceStatus,
  selectVoiceDevice,
  startVoiceListener,
  stopVoiceListener,
} from '../services/voiceApi';
import type {
  VoiceErrorPayload,
  VoiceServiceStatus,
  VoiceStatus,
  VoiceStatusChangedPayload,
  VoiceWakeDetectedPayload,
} from '../types/voice';
import type { WebSocketMessage } from '../types/messages';

const ACTIVATION_BANNER_MS = 1100;

export interface UseVoiceStatusResult {
  voiceStatus: VoiceStatus | null;
  loading: boolean;
  error: string | null;
  pending: boolean;
  activationVisible: boolean;
  lastWake: VoiceWakeDetectedPayload | null;
  refresh: () => Promise<void>;
  start: () => Promise<void>;
  stop: () => Promise<void>;
  selectDevice: (deviceId: number) => Promise<void>;
  handleSocketMessage: (message: WebSocketMessage) => void;
}

function mergeStatusPatch(
  previous: VoiceStatus | null,
  patch: VoiceStatusChangedPayload,
): VoiceStatus {
  const base: VoiceStatus = previous ?? {
    enabled: patch.enabled ?? true,
    status: patch.status,
    wake_phrase: patch.wake_phrase ?? 'Wake up Jarvis',
    model_loaded: patch.model_loaded ?? false,
    model_path: '',
    microphone: patch.microphone_name
      ? { id: null, name: patch.microphone_name, is_default: false }
      : null,
    last_activation_at: patch.last_activation_at ?? null,
    last_error: patch.last_error ?? null,
  };

  return {
    ...base,
    status: patch.status,
    enabled: patch.enabled ?? base.enabled,
    model_loaded: patch.model_loaded ?? base.model_loaded,
    wake_phrase: patch.wake_phrase ?? base.wake_phrase,
    last_error: patch.last_error !== undefined ? patch.last_error : base.last_error,
    last_activation_at:
      patch.last_activation_at !== undefined
        ? patch.last_activation_at
        : base.last_activation_at,
    microphone: patch.microphone_name
      ? {
          id: base.microphone?.id ?? null,
          name: patch.microphone_name,
          is_default: base.microphone?.is_default ?? false,
        }
      : base.microphone,
  };
}

export function useVoiceStatus(): UseVoiceStatusResult {
  const [voiceStatus, setVoiceStatus] = useState<VoiceStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [activationVisible, setActivationVisible] = useState(false);
  const [lastWake, setLastWake] = useState<VoiceWakeDetectedPayload | null>(null);
  const bannerTimer = useRef<number | null>(null);

  const clearBannerTimer = () => {
    if (bannerTimer.current !== null) {
      window.clearTimeout(bannerTimer.current);
      bannerTimer.current = null;
    }
  };

  const showActivation = useCallback((payload: VoiceWakeDetectedPayload) => {
    setLastWake(payload);
    setActivationVisible(true);
    clearBannerTimer();
    bannerTimer.current = window.setTimeout(() => {
      setActivationVisible(false);
      bannerTimer.current = null;
    }, ACTIVATION_BANNER_MS);
  }, []);

  const refresh = useCallback(async () => {
    try {
      const status = await fetchVoiceStatus();
      setVoiceStatus(status);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to load voice status');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
    return () => clearBannerTimer();
  }, [refresh]);

  const start = useCallback(async () => {
    setPending(true);
    setError(null);
    try {
      const status = await startVoiceListener();
      setVoiceStatus(status);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start listener');
      await refresh();
    } finally {
      setPending(false);
    }
  }, [refresh]);

  const stop = useCallback(async () => {
    setPending(true);
    setError(null);
    try {
      const status = await stopVoiceListener();
      setVoiceStatus(status);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to stop listener');
      await refresh();
    } finally {
      setPending(false);
    }
  }, [refresh]);

  const selectDevice = useCallback(
    async (deviceId: number) => {
      setPending(true);
      setError(null);
      try {
        const status = await selectVoiceDevice(deviceId);
        setVoiceStatus(status);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to change microphone');
        await refresh();
      } finally {
        setPending(false);
      }
    },
    [refresh],
  );

  const handleSocketMessage = useCallback(
    (message: WebSocketMessage) => {
      if (message.type === 'voice.status_changed') {
        const payload = message.payload as unknown as VoiceStatusChangedPayload;
        setVoiceStatus((prev) => mergeStatusPatch(prev, payload));
        setLoading(false);
        return;
      }

      if (message.type === 'voice.wake_detected') {
        const payload = message.payload as unknown as VoiceWakeDetectedPayload;
        showActivation(payload);
        return;
      }

      if (message.type === 'voice.error') {
        const payload = message.payload as unknown as VoiceErrorPayload;
        setError(payload.message);
        setVoiceStatus((prev) =>
          prev
            ? { ...prev, last_error: payload.message, status: prev.status }
            : prev,
        );
      }
    },
    [showActivation],
  );

  return {
    voiceStatus,
    loading,
    error,
    pending,
    activationVisible,
    lastWake,
    refresh,
    start,
    stop,
    selectDevice,
    handleSocketMessage,
  };
}

export function describeVoiceStatus(status: VoiceServiceStatus | undefined): string {
  switch (status) {
    case 'LOADING_MODEL':
      return 'Loading model';
    case 'LISTENING':
      return 'Listening';
    case 'ACTIVATION_DETECTED':
      return 'Activation detected';
    case 'STOPPED':
      return 'Stopped';
    case 'DISABLED':
      return 'Disabled';
    case 'MODEL_MISSING':
      return 'Model missing';
    case 'STARTING':
      return 'Starting';
    case 'STOPPING':
      return 'Stopping';
    case 'ERROR':
      return 'Error';
    default:
      return 'Unknown';
  }
}
