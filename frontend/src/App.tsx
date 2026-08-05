import { Navigate, Outlet, Route, Routes } from 'react-router-dom';

import { DashboardShell } from './components/dashboard/DashboardShell';
import { PanelViewport } from './components/dashboard/PanelViewport';
import { DashboardProvider } from './context/DashboardContext';
import { SettingsPage } from './pages/SettingsPage';

function EmptyPanelRoute() {
  return null;
}

function PanelLayout() {
  return (
    <DashboardShell>
      <PanelViewport />
      <Outlet />
    </DashboardShell>
  );
}

function SettingsLayout() {
  return (
    <DashboardShell mode="settings">
      <SettingsPage />
    </DashboardShell>
  );
}

export default function App() {
  return (
    <DashboardProvider>
      <Routes>
        <Route element={<PanelLayout />}>
          <Route path="/" element={<EmptyPanelRoute />} />
          <Route path="/applications" element={<EmptyPanelRoute />} />
          <Route path="/system" element={<EmptyPanelRoute />} />
        </Route>
        <Route path="/settings" element={<SettingsLayout />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </DashboardProvider>
  );
}
