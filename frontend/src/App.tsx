import { useEffect } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';

import { DashboardLayout } from './components/layout/DashboardLayout';
import { useJarvisSocket } from './hooks/useJarvisSocket';
import { useSpeechStatus } from './hooks/useSpeechStatus';
import { useVoiceStatus } from './hooks/useVoiceStatus';
import { ApplicationsPage } from './pages/ApplicationsPage';
import { HomePage } from './pages/HomePage';
import { SettingsPage } from './pages/SettingsPage';
import { SystemPage } from './pages/SystemPage';
import type { WebSocketMessage } from './types/messages';

export default function App() {
  const { connectionStatus, assistantState, activity, registerMessageHandler } =
    useJarvisSocket();
  const voice = useVoiceStatus();
  const speech = useSpeechStatus();

  useEffect(() => {
    const handler = (message: WebSocketMessage) => {
      voice.handleSocketMessage(message);
      speech.handleSocketMessage(message);
    };
    registerMessageHandler(handler);
    return () => registerMessageHandler(null);
  }, [registerMessageHandler, voice.handleSocketMessage, speech.handleSocketMessage]);

  useEffect(() => {
    if (connectionStatus === 'CONNECTED') {
      void voice.refresh();
      void speech.refresh();
    }
  }, [connectionStatus, voice.refresh, speech.refresh]);

  return (
    <DashboardLayout connectionStatus={connectionStatus}>
      <Routes>
        <Route
          path="/"
          element={
            <HomePage
              connectionStatus={connectionStatus}
              assistantState={assistantState}
              activity={activity}
              voiceStatus={voice.voiceStatus}
              voiceLoading={voice.loading}
              voiceError={voice.error}
              voicePending={voice.pending}
              activationVisible={voice.activationVisible}
              onStartListener={() => void voice.start()}
              onStopListener={() => void voice.stop()}
              ttsStatus={speech.ttsStatus}
              ttsLoading={speech.loading}
              ttsError={speech.error}
              ttsPending={speech.pending}
              currentUtterance={speech.currentUtterance}
              initializingVisible={speech.initializingVisible}
              sequenceCompleteVisible={speech.sequenceCompleteVisible}
              speaking={speech.speaking}
              onTestWelcome={() => void speech.testWelcome()}
              onCancelSpeech={() => void speech.cancel()}
              onRetryTts={() => void speech.retry()}
            />
          }
        />
        <Route
          path="/system"
          element={
            <SystemPage voiceStatus={voice.voiceStatus} ttsStatus={speech.ttsStatus} />
          }
        />
        <Route path="/applications" element={<ApplicationsPage />} />
        <Route
          path="/settings"
          element={
            <SettingsPage
              voiceStatus={voice.voiceStatus}
              voiceLoading={voice.loading}
              voiceError={voice.error}
              voicePending={voice.pending}
              onStart={() => void voice.start()}
              onStop={() => void voice.stop()}
              onSelectDevice={(id) => void voice.selectDevice(id)}
              onRetry={() => void voice.start()}
              ttsStatus={speech.ttsStatus}
              ttsLoading={speech.loading}
              ttsError={speech.error}
              ttsPending={speech.pending}
              onSelectOutputDevice={(id) => void speech.selectDevice(id)}
              onTestWelcome={() => void speech.testWelcome()}
              onCancelSpeech={() => void speech.cancel()}
              onRetryTts={() => void speech.retry()}
            />
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </DashboardLayout>
  );
}
