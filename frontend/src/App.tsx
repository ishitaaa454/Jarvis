import { Navigate, Route, Routes } from 'react-router-dom';

import { DashboardLayout } from './components/layout/DashboardLayout';
import { useJarvisSocket } from './hooks/useJarvisSocket';
import { ApplicationsPage } from './pages/ApplicationsPage';
import { HomePage } from './pages/HomePage';
import { SettingsPage } from './pages/SettingsPage';
import { SystemPage } from './pages/SystemPage';

export default function App() {
  const { connectionStatus, assistantState, activity } = useJarvisSocket();

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
            />
          }
        />
        <Route path="/system" element={<SystemPage />} />
        <Route path="/applications" element={<ApplicationsPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </DashboardLayout>
  );
}
