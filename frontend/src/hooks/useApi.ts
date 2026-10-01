import { useCallback, useState } from 'react';

export const API_BASE_URL =
  import.meta.env.VITE_API_URL ||
  'http://localhost:8000';

interface ApiOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH';
  headers?: Record<string, string>;
  body?: FormData | string | URLSearchParams | null;
  requiresAuth?: boolean;
  responseType?: 'json' | 'blob';
}

interface ApiError {
  detail?: string | any[];
  errors?: unknown[];
  error_code?: string;
}

export class UnauthorizedError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'UnauthorizedError';
  }
}

export function useApi() {
  const [isRateLimited, setIsRateLimited] = useState<boolean>(false);

  const getToken = (): string | null => {
    return localStorage.getItem('access_token');
  };

  const setToken = (token: string): void => {
    localStorage.setItem('access_token', token);
  };

  const removeToken = (): void => {
    localStorage.removeItem('access_token');
  };

  const request = useCallback(async <T = unknown>(
    endpoint: string,
    options: ApiOptions = {}
  ): Promise<T> => {
    const {
      method = 'GET',
      headers = {},
      body = null,
      requiresAuth = true
    } = options;

    const requestHeaders: Record<string, string> = {
      ...headers
    };

    if (requiresAuth) {
      const token = getToken();
      if (token) {
        requestHeaders['Authorization'] = `Bearer ${token}`;
      }
    }

    if (body instanceof FormData) {
      // Don't set Content-Type for FormData, browser will set it with boundary
    } else if (body instanceof URLSearchParams) {
      requestHeaders['Content-Type'] = 'application/x-www-form-urlencoded';
    } else if (body) {
      requestHeaders['Content-Type'] = 'application/json';
    }

    let response: Response;
    try {
      response = await fetch(`${API_BASE_URL}${endpoint}`, {
        method,
        headers: requestHeaders,
        body: body instanceof URLSearchParams ? body.toString() : (body instanceof FormData ? body : body)
      });
    } catch (e) {
      throw new Error("Cannot reach the server.");
    }

    if (!response.ok) {
      if (response.status === 429) {
        const retryAfter = response.headers.get('Retry-After');
        let seconds = 60;
        let msg = "Too many requests. Please try again in a minute.";
        if (retryAfter) {
          const parsed = parseInt(retryAfter, 10);
          if (!isNaN(parsed)) {
            seconds = parsed;
            msg = `Too many requests. Please try again in ${seconds} seconds.`;
          }
        }
        setIsRateLimited(true);
        setTimeout(() => setIsRateLimited(false), seconds * 1000);
        throw new Error(msg);
      }

      if (response.status === 401) {
        if (endpoint === '/login') {
          throw new Error('Incorrect username or password.');
        } else {
          removeToken();
          // Dispatch event so App/Auth can react if needed, or simply throw error
          window.dispatchEvent(new Event('auth:unauthorized'));
          throw new UnauthorizedError('Your session has expired. Please sign in again.');
        }
      }

      if (response.status === 403) {
        throw new Error("You do not have permission to do this.");
      }

      if (response.status === 404) {
        throw new Error("That item was not found.");
      }

      if (response.status === 413) {
        throw new Error("File is larger than the 10 MB limit.");
      }

      if (response.status >= 500) {
        throw new Error("Something went wrong on our side. Please try again.");
      }

      let errorData: ApiError = {};
      try {
        errorData = await response.json();
      } catch {
        // failed to parse
      }

      if (response.status === 422 && Array.isArray(errorData.detail)) {
        const messages = errorData.detail.map((err: any) => {
          const loc = err.loc ? err.loc.join('.') : 'Field';
          return `${loc}: ${err.msg}`;
        }).join(', ');
        throw new Error(messages);
      }

      if (typeof errorData.detail === 'string') {
        throw new Error(errorData.detail);
      }
      
      throw new Error(`Request failed with status ${response.status}`);
    }

    if (response.status === 204) {
      return undefined as T;
    }

    if (options.responseType === 'blob') {
      return response.blob() as unknown as Promise<T>;
    }

    return response.json() as Promise<T>;
  }, []);

  return {
    request,
    getToken,
    setToken,
    removeToken,
    API_BASE_URL,
    isRateLimited
  };
}
