import React from 'react';
import { Shield, Files, History, Bell, LogOut } from 'lucide-react';
import type { User } from '../../hooks/useAuth';

export type AppTab = 'files' | 'history' | 'alerts' | 'admin';

interface AppShellProps {
  user: User;
  activeTab: AppTab;
  onTabChange: (tab: AppTab) => void;
  onLogout: () => void;
  children: React.ReactNode;
}

const NAV: { tab: AppTab; label: string; icon: React.ReactNode; adminOnly?: boolean }[] = [
  { tab: 'files',   label: 'My Files',       icon: <Files   size={15} strokeWidth={1.75} /> },
  { tab: 'history', label: 'Access History',  icon: <History size={15} strokeWidth={1.75} /> },
  { tab: 'alerts',  label: 'Security Alerts', icon: <Bell    size={15} strokeWidth={1.75} /> },
  { tab: 'admin',   label: 'Admin',           icon: <Shield  size={15} strokeWidth={1.75} />, adminOnly: true },
];

function roleLabel(role: string): string {
  if (role === 'admin')   return 'Admin';
  if (role === 'auditor') return 'Auditor';
  return 'User';
}

export function AppShell({ user, activeTab, onTabChange, onLogout, children }: AppShellProps) {
  const visibleNav = NAV.filter(n => !n.adminOnly || user.role === 'admin');

  return (
    <div className="app-shell">
      {/* ── Header ────────────────────────────────────────── */}
      <header className="app-header" role="banner">
        <div className="app-header-inner">
          {/* Wordmark */}
          <a href="#" className="app-wordmark" aria-label="Secure File Sharing — home">
            Secure<span>File</span>
          </a>

          {/* Navigation */}
          <nav className="app-nav" aria-label="Main navigation">
            {visibleNav.map(({ tab, label, icon }) => (
              <button
                key={tab}
                className={`nav-link${activeTab === tab ? ' active' : ''}`}
                onClick={() => onTabChange(tab)}
                aria-current={activeTab === tab ? 'page' : undefined}
                id={`nav-${tab}`}
              >
                {icon}
                <span>{label}</span>
              </button>
            ))}
          </nav>

          {/* User info + logout */}
          <div className="app-header-end">
            <div className="user-chip" aria-label={`Signed in as ${user.username}, role: ${roleLabel(user.role)}`}>
              <span>{user.username}</span>
              <span className="user-chip-role">{roleLabel(user.role)}</span>
            </div>
            <button
              className="btn btn-ghost btn-sm"
              onClick={onLogout}
              aria-label="Sign out"
              title="Sign out"
              id="btn-logout"
            >
              <LogOut size={14} strokeWidth={1.75} aria-hidden="true" />
              <span style={{ display: 'none' }}>Sign out</span>
            </button>
          </div>
        </div>
      </header>

      {/* ── Main content ──────────────────────────────────── */}
      <main className="app-main" id="main-content">
        {children}
      </main>

      {/* ── Footer ────────────────────────────────────────── */}
      <footer className="app-footer" role="contentinfo">
        <div className="app-footer-inner">
          <span>All files are encrypted at rest. Integrity is anchored to the Sepolia testnet.</span>
          <span style={{ marginLeft: 'auto', paddingLeft: '1rem' }}>
            Secure File Sharing
          </span>
        </div>
      </footer>
    </div>
  );
}
