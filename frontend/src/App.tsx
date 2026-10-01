import { useState, useEffect } from 'react';
import { useApi } from './hooks/useApi';
import { AppShell } from './components/layout/AppShell';
import type { AppTab } from './components/layout/AppShell';
import { Auth } from './components/Auth';
import { FileDashboard } from './components/FileDashboard';
import { AccessHistory } from './components/AccessHistory';
import { SecurityAlerts } from './components/SecurityAlerts';
import { AdminPanel } from './components/AdminPanel';

interface UserInfo {
  id: number;
  username: string;
  email: string;
  role: string;
  created_at: string;
}

function App() {
  const { request, removeToken } = useApi();
  const [user, setUser] = useState<UserInfo | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<AppTab>('files');

  const fetchCurrentUser = async () => {
    const token = localStorage.getItem('access_token');
    if (!token) return null;
    try {
      const userData = await request<UserInfo>('/users/me', { requiresAuth: true });
      return userData;
    } catch {
      removeToken();
      return null;
    }
  };

  useEffect(() => {
    fetchCurrentUser().then(u => {
      setUser(u);
      setIsLoading(false);
    });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const handleAuthSuccess = async () => {
    const u = await fetchCurrentUser();
    setUser(u);
  };

  const handleLogout = () => {
    removeToken();
    setUser(null);
    setActiveTab('files');
  };

  // ── Loading splash ────────────────────────────────────────
  if (isLoading) {
    return (
      <div
        style={{
          minHeight: '100dvh',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          backgroundColor: 'var(--color-parchment)',
          flexDirection: 'column',
          gap: '1rem',
        }}
      >
        <span className="spinner" style={{ width: '1.5rem', height: '1.5rem' }} role="status" aria-label="Loading" />
        <p style={{ color: 'var(--color-muted)', fontSize: '0.875rem' }}>Loading…</p>
      </div>
    );
  }

  // ── Auth screens ──────────────────────────────────────────
  if (!user) {
    return <Auth onAuthSuccess={handleAuthSuccess} />;
  }

  // ── Tab renderer ──────────────────────────────────────────
  const renderTab = () => {
    switch (activeTab) {
      case 'files':
        return <FileDashboard onLogout={handleLogout} />;
      case 'history':
        return <AccessHistory />;
      case 'alerts':
        return <SecurityAlerts user={user} />;
      case 'admin':
        return <AdminPanel />;
      default:
        return <FileDashboard onLogout={handleLogout} />;
    }
  };

  return (
    <AppShell
      user={user}
      activeTab={activeTab}
      onTabChange={setActiveTab}
      onLogout={handleLogout}
    >
      {renderTab()}
    </AppShell>
  );
}

export default App;
