import { useState, useCallback, useEffect } from 'react';
import { useApi } from './useApi';

export interface User {
  id: number;
  username: string;
  email: string;
  role: string;
  created_at: string;
}

interface LoginCredentials {
  username: string;
  password: string;
}

interface RegisterData {
  username: string;
  email: string;
  password: string;
}

interface TokenResponse {
  access_token: string;
  token_type: string;
}

export function useAuth() {
  const { request, setToken, removeToken, isRateLimited } = useApi();
  const [user, setUser] = useState<User | null>(null);
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Check authentication status on mount
  useEffect(() => {
    const checkAuth = async () => {
      const token = localStorage.getItem('access_token');
      if (token) {
        try {
          const userData = await request<User>('/users/me', { requiresAuth: true });
          setUser(userData);
          setIsAuthenticated(true);
        } catch {
          // Token invalid or expired
          removeToken();
          setUser(null);
          setIsAuthenticated(false);
        }
      }
      setIsLoading(false);
    };

    checkAuth();
  }, [request, removeToken]);

  useEffect(() => {
    const handleUnauthorized = () => {
      setUser(null);
      setIsAuthenticated(false);
      setError('Your session has expired. Please sign in again.');
    };
    window.addEventListener('auth:unauthorized', handleUnauthorized);
    return () => window.removeEventListener('auth:unauthorized', handleUnauthorized);
  }, []);

  const login = useCallback(async (credentials: LoginCredentials): Promise<void> => {
    setError(null);
    setIsLoading(true);

    try {
      const formData = new URLSearchParams();
      formData.append('username', credentials.username);
      formData.append('password', credentials.password);

      const tokenData = await request<TokenResponse>('/login', {
        method: 'POST',
        body: formData,
        requiresAuth: false
      });

      setToken(tokenData.access_token);

      const userData = await request<User>('/users/me', { requiresAuth: true });
      setUser(userData);
      setIsAuthenticated(true);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Login failed';
      setError(errorMessage);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, [request, setToken]);

  const register = useCallback(async (data: RegisterData): Promise<void> => {
    setError(null);
    setIsLoading(true);

    try {
      await request<User>('/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
        requiresAuth: false
      });
      // After successful registration, log the user in
      await login({ username: data.username, password: data.password });
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Registration failed';
      setError(errorMessage);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, [request, login]);

  const logout = useCallback((): void => {
    removeToken();
    setUser(null);
    setIsAuthenticated(false);
    setError(null);
  }, [removeToken]);

  return {
    user,
    isAuthenticated,
    isLoading,
    error,
    login,
    register,
    logout,
    isRateLimited
  };
}
