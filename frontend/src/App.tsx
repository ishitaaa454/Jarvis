import { useEffect } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';

import { DashboardLayout } from './components/layout/DashboardLayout';
import { useJarvisSocket } from './hooks/useJarvisSocket';
import { useSpeechStatus } from './hooks/useSpeechStatus';
import { useVoiceStatus } from './hooks/useVoiceStatus';
import { useWorkspaceStatus } from './hooks/useWorkspaceStatus';
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
  const workspace = useWorkspaceStatus();

  useEffect(() => {
    const handler = (message: WebSocketMessage) => {
      voice.handleSocketMessage(message);
      speech.handleSocketMessage(message);
      workspace.handleSocketMessage(message);
    };
    registerMessageHandler(handler);
    return () => registerMessageHandler(null);
  }, [
    registerMessageHandler,
    voice.handleSocketMessage,
    speech.handleSocketMessage,
    workspace.handleSocketMessage,
  ]);

  useEffect(() => {
    if (connectionStatus === 'CONNECTED') {
      void voice.refresh();
      void speech.refresh();
      void workspace.refresh();
    }
  }, [connectionStatus, voice.refresh, speech.refresh, workspace.refresh]);

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
              workspaceStatus={workspace.workspaceStatus}
              workspaceApplications={workspace.applications}
              workspaceLoading={workspace.loading}
              workspaceError={workspace.error}
              workspacePending={workspace.pending}
              workspacePendingAppIds={workspace.pendingAppIds}
              workspaceBanner={workspace.banner}
              workspaceRunning={workspace.isRunning}
              onStartWorkspace={() => void workspace.start()}
              onCancelWorkspace={() => void workspace.cancel()}
              onRefreshWorkspace={() => void workspace.reloadRegistry()}
              onOpenWorkspaceApp={(appId) => void workspace.openApp(appId)}
              onFocusWorkspaceApp={(appId) => void workspace.focusApp(appId)}
            />
          }
        />
        <Route
          path="/system"
          element={
            <SystemPage
              voiceStatus={voice.voiceStatus}
              ttsStatus={speech.ttsStatus}
              workspaceStatus={workspace.workspaceStatus}
              workspaceApplications={workspace.applications}
            />
          }
        />
        <Route
          path="/applications"
          element={
            <ApplicationsPage
              applications={workspace.applications}
              loading={workspace.loading}
              error={workspace.error}
              pendingAppIds={workspace.pendingAppIds}
              onOpenApp={(appId) => void workspace.openApp(appId)}
              onFocusApp={(appId) => void workspace.focusApp(appId)}
            />
          }
        />
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
              workspaceApplications={workspace.applications}
              workspaceLoading={workspace.loading}
            />
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </DashboardLayout>
  );
}
