import { useEffect } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';

import { DashboardLayout } from './components/layout/DashboardLayout';
import { useJarvisSocket } from './hooks/useJarvisSocket';
import { useVoiceStatus } from './hooks/useVoiceStatus';
import { ApplicationsPage } from './pages/ApplicationsPage';
import { HomePage } from './pages/HomePage';
import { SettingsPage } from './pages/SettingsPage';
import { SystemPage } from './pages/SystemPage';

export default function App() {
  const { connectionStatus, assistantState, activity, registerMessageHandler } =
    useJarvisSocket();
  const voice = useVoiceStatus();

  useEffect(() => {
    registerMessageHandler(voice.handleSocketMessage);
    return () => registerMessageHandler(null);
  }, [registerMessageHandler, voice.handleSocketMessage]);

  // Refresh voice status after reconnect so REST + WS stay aligned
  useEffect(() => {
    if (connectionStatus === 'CONNECTED') {
      void voice.refresh();
    }
  }, [connectionStatus, voice.refresh]);

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
            />
          }
        />
        <Route
          path="/system"
          element={<SystemPage voiceStatus={voice.voiceStatus} />}
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
            />
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </DashboardLayout>
  );
}
