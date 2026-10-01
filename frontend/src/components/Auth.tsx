import { useState } from 'react';
import { useAuth } from '../hooks/useAuth';
import { Input } from './ui/Input';
import { Button } from './ui/Button';
import { ErrorMessage } from './ui/ErrorMessage';

interface AuthProps {
  onAuthSuccess: () => void;
}

export function Auth({ onAuthSuccess }: AuthProps) {
  const [isLogin, setIsLogin] = useState(true);
  const [formData, setFormData] = useState({
    username: '',
    email: '',
    password: '',
    confirmPassword: ''
  });

  const { login, register, isLoading, error, isRateLimited } = useAuth();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    try {
      if (isLogin) {
        await login({
          username: formData.username,
          password: formData.password
        });
      } else {
        if (formData.password !== formData.confirmPassword) {
          return;
        }
        await register({
          username: formData.username,
          email: formData.email,
          password: formData.password,
        });
      }
      onAuthSuccess();
    } catch {
      // Error is handled by the hook and exposed via `error`
    }
  };

  const toggleMode = () => {
    setIsLogin(!isLogin);
    setFormData({
      username: '',
      email: '',
      password: '',
      confirmPassword: ''
    });
  };

  return (
    <div className="auth-page">
      <div className="auth-card">
        <h1 className="auth-card-title">Secure<span style={{ color: 'var(--color-pine)' }}>File</span></h1>
        <p className="auth-card-sub" style={{ textTransform: 'uppercase', letterSpacing: '0.05em', fontSize: '0.75rem', fontWeight: 600 }}>
          {isLogin ? 'Sign in to your account' : 'Create a new account'}
        </p>

        {error && (
          <ErrorMessage variant="error" className="mb-4" style={{ marginBottom: '1.25rem' }}>
            {error}
          </ErrorMessage>
        )}
        
        {(!isLogin && formData.password !== formData.confirmPassword && formData.confirmPassword !== '') && (
          <ErrorMessage variant="error" className="mb-4" style={{ marginBottom: '1.25rem' }}>
            Passwords do not match
          </ErrorMessage>
        )}

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <Input
            id="username"
            label="Username"
            required
            value={formData.username}
            onChange={(e) => setFormData({ ...formData, username: e.target.value })}
            placeholder="e.g. alice_smith"
          />

          {!isLogin && (
            <Input
              id="email"
              type="email"
              label="Email Address"
              required
              value={formData.email}
              onChange={(e) => setFormData({ ...formData, email: e.target.value })}
              placeholder="alice@example.com"
            />
          )}

          <Input
            id="password"
            type="password"
            label="Password"
            required
            value={formData.password}
            onChange={(e) => setFormData({ ...formData, password: e.target.value })}
          />

          {!isLogin && (
            <Input
              id="confirmPassword"
              type="password"
              label="Confirm Password"
              required
              value={formData.confirmPassword}
              onChange={(e) => setFormData({ ...formData, confirmPassword: e.target.value })}
            />
          )}

          <div style={{ marginTop: '0.5rem' }}>
            <Button
              type="submit"
              variant="primary"
              loading={isLoading}
              disabled={isRateLimited}
              style={{ width: '100%' }}
            >
              {isLogin ? 'Sign In' : 'Create Account'}
            </Button>
          </div>
        </form>

        <div style={{ marginTop: '2rem', textAlign: 'center', borderTop: '1px solid var(--color-rule)', paddingTop: '1.25rem' }}>
          <p style={{ fontSize: '0.8125rem', color: 'var(--color-muted)' }}>
            {isLogin ? "Don't have an account? " : "Already have an account? "}
            <button
              type="button"
              onClick={toggleMode}
              style={{
                background: 'none',
                border: 'none',
                color: 'var(--color-pine)',
                fontWeight: 600,
                cursor: 'pointer',
                padding: 0
              }}
            >
              {isLogin ? 'Register' : 'Sign in'}
            </button>
          </p>
        </div>
      </div>
    </div>
  );
}
