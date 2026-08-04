import { useCallback, useEffect, useRef, useState } from 'react';

import {
  cancelSpeech,
  fetchTtsStatus,
  retryTts,
  selectTtsDevice,
  testWelcomeSequence,
} from '../services/ttsApi';
import type { TtsStatus, UtteranceProgress } from '../types/speech';
import type { WebSocketMessage } from '../types/messages';

const COMPLETE_BANNER_MS = 1600;

export interface UseSpeechStatusResult {
  ttsStatus: TtsStatus | null;
  loading: boolean;
  error: string | null;
  pending: boolean;
  currentUtterance: UtteranceProgress | null;
  sequenceCompleteVisible: boolean;
  initializingVisible: boolean;
  speaking: boolean;
  refresh: () => Promise<void>;
  testWelcome: () => Promise<void>;
  cancel: () => Promise<void>;
  retry: () => Promise<void>;
  selectDevice: (deviceId: number) => Promise<void>;
  handleSocketMessage: (message: WebSocketMessage) => void;
}

export function useSpeechStatus(): UseSpeechStatusResult {
  const [ttsStatus, setTtsStatus] = useState<TtsStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [currentUtterance, setCurrentUtterance] = useState<UtteranceProgress | null>(null);
  const [sequenceCompleteVisible, setSequenceCompleteVisible] = useState(false);
  const [initializingVisible, setInitializingVisible] = useState(false);
  const completeTimer = useRef<number | null>(null);

  const refresh = useCallback(async () => {
    try {
      const status = await fetchTtsStatus();
      setTtsStatus(status);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to load TTS status');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
    return () => {
      if (completeTimer.current) window.clearTimeout(completeTimer.current);
    };
  }, [refresh]);

  const testWelcome = useCallback(async () => {
    setPending(true);
    setError(null);
    setInitializingVisible(true);
    try {
      const status = await testWelcomeSequence();
      setTtsStatus(status);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Welcome sequence failed');
      await refresh();
    } finally {
      setPending(false);
      setInitializingVisible(false);
    }
  }, [refresh]);

  const cancel = useCallback(async () => {
    setPending(true);
    try {
      const status = await cancelSpeech();
      setTtsStatus(status);
      setCurrentUtterance(null);
      setInitializingVisible(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Cancel failed');
    } finally {
      setPending(false);
    }
  }, []);

  const retry = useCallback(async () => {
    setPending(true);
    try {
      const status = await retryTts();
      setTtsStatus(status);
      setError(status.last_error);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Retry failed');
    } finally {
      setPending(false);
    }
  }, []);

  const selectDevice = useCallback(
    async (deviceId: number) => {
      setPending(true);
      try {
        const status = await selectTtsDevice(deviceId);
        setTtsStatus(status);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Device change failed');
        await refresh();
      } finally {
        setPending(false);
      }
    },
    [refresh],
  );

  const handleSocketMessage = useCallback((message: WebSocketMessage) => {
    if (message.type === 'tts.status_changed') {
      const payload = message.payload as Record<string, unknown>;
      setTtsStatus((prev) => ({
        enabled: prev?.enabled ?? true,
        status: (payload.status as TtsStatus['status']) ?? prev?.status ?? 'STOPPED',
        engine: (payload.engine as string) ?? prev?.engine ?? 'Piper',
        voice: (payload.voice as string) ?? prev?.voice ?? 'en_GB-alan-medium',
        model_loaded: Boolean(payload.model_loaded ?? prev?.model_loaded),
        output_device: payload.output_device_name
          ? {
              id: prev?.output_device?.id ?? null,
              name: String(payload.output_device_name),
              is_default: prev?.output_device?.is_default ?? false,
            }
          : prev?.output_device ?? null,
        is_speaking: Boolean(payload.is_speaking),
        current_sequence: (payload.current_sequence as string | null) ?? null,
        current_utterance_index:
          (payload.current_utterance_index as number | null) ?? null,
        last_spoken_at: (payload.last_spoken_at as string | null) ?? prev?.last_spoken_at ?? null,
        last_error: (payload.last_error as string | null) ?? null,
        microphone_suppressed: Boolean(payload.microphone_suppressed),
      }));
      setLoading(false);
      return;
    }

    if (message.type === 'tts.sequence_started') {
      setInitializingVisible(true);
      setSequenceCompleteVisible(false);
      setCurrentUtterance(null);
      return;
    }

    if (message.type === 'tts.utterance_started') {
      setInitializingVisible(false);
      const payload = message.payload as unknown as UtteranceProgress;
      setCurrentUtterance(payload);
      return;
    }

    if (message.type === 'tts.utterance_finished') {
      return;
    }

    if (message.type === 'tts.sequence_finished') {
      setCurrentUtterance(null);
      setInitializingVisible(false);
      setSequenceCompleteVisible(true);
      if (completeTimer.current) window.clearTimeout(completeTimer.current);
      completeTimer.current = window.setTimeout(() => {
        setSequenceCompleteVisible(false);
      }, COMPLETE_BANNER_MS);
      return;
    }

    if (message.type === 'tts.sequence_cancelled' || message.type === 'tts.error') {
      setCurrentUtterance(null);
      setInitializingVisible(false);
      if (message.type === 'tts.error') {
        const payload = message.payload as { message?: string };
        if (payload.message) setError(payload.message);
      }
    }
  }, []);

  const speaking =
    ttsStatus?.is_speaking === true ||
    ttsStatus?.status === 'SPEAKING' ||
    ttsStatus?.status === 'SYNTHESIZING' ||
    currentUtterance !== null;

  return {
    ttsStatus,
    loading,
    error,
    pending,
    currentUtterance,
    sequenceCompleteVisible,
    initializingVisible,
    speaking,
    refresh,
    testWelcome,
    cancel,
    retry,
    selectDevice,
    handleSocketMessage,
  };
}

export function describeTtsStatus(status: TtsStatus['status'] | undefined): string {
  switch (status) {
    case 'READY':
      return 'Ready';
    case 'SPEAKING':
      return 'Speaking';
    case 'SYNTHESIZING':
      return 'Synthesizing';
    case 'MODEL_MISSING':
      return 'Model missing';
    case 'ENGINE_MISSING':
      return 'Piper missing';
    case 'OUTPUT_UNAVAILABLE':
      return 'No output device';
    case 'DISABLED':
      return 'Disabled';
    case 'ERROR':
      return 'Error';
    case 'VALIDATING':
      return 'Validating';
    default:
      return status ?? 'Unknown';
  }
}
