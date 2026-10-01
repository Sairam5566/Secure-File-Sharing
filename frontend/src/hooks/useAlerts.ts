import { useState, useEffect, useCallback, useRef } from 'react';
import { useApi } from './useApi';

export interface SecurityAlert {
  id: string;
  message: string;
  timestamp: string;
  details?: {
    user_id?: number;
    file_id?: number;
    action_type?: string;
    ip_address?: string | null;
    device_info?: string | null;
    anomaly_score?: number | null;
  };
}

interface AccessLog {
  id: number;
  user_id: number;
  file_id: number | null;
  access_time: string;
  access_status: string;
  ip_address: string | null;
  device_info: string | null;
  action_type: string;
  is_anomalous: boolean;
  anomaly_score: number | null;
}

export function useAlerts(pollInterval: number = 60000, limit: number = 20) {
  const { request } = useApi();
  const [alerts, setAlerts] = useState<SecurityAlert[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [offset, setOffset] = useState<number>(0);
  const [hasMore, setHasMore] = useState<boolean>(true);
  const [stopPolling, setStopPolling] = useState<boolean>(false);
  const isFetchingRef = useRef<boolean>(false);

  const fetchAlerts = useCallback(async (isLoadMore: boolean = false): Promise<void> => {
    if (isFetchingRef.current) return;
    
    setIsLoading(true);
    setError(null);
    isFetchingRef.current = true;

    try {
      const currentOffset = isLoadMore ? offset : 0;
      const anomalousLogs = await request<AccessLog[]>(
        `/access-logs/?is_anomalous=true&limit=${limit}&offset=${currentOffset}`, 
        { requiresAuth: true }
      );

      const mappedAlerts: SecurityAlert[] = anomalousLogs.map(log => {
        return {
          id: `log-${log.id}`,
          message: `Anomalous activity detected: ${log.action_type} ${log.access_status === 'denied' ? '(Blocked)' : ''}`,
          timestamp: log.access_time,
          details: {
            user_id: log.user_id,
            file_id: log.file_id || undefined,
            action_type: log.action_type,
            ip_address: log.ip_address,
            device_info: log.device_info,
            anomaly_score: log.anomaly_score
          }
        };
      });

      if (isLoadMore) {
        setAlerts(prev => [...prev, ...mappedAlerts]);
        setOffset(prev => prev + limit);
      } else {
        setAlerts(mappedAlerts);
        setOffset(limit);
      }
      
      setHasMore(anomalousLogs.length === limit);
      
      // Clear any rate limit flags if successful
      setStopPolling(false);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to fetch alerts';
      setError(errorMessage);
      if (errorMessage.includes('Too many requests') || errorMessage.includes('429')) {
        setStopPolling(true);
      }
    } finally {
      setIsLoading(false);
      isFetchingRef.current = false;
    }
  }, [request, limit, offset]);

  const dismissAlert = useCallback((alertId: string): void => {
    setAlerts(prev => prev.filter(alert => alert.id !== alertId));
  }, []);

  const clearAllAlerts = useCallback((): void => {
    setAlerts([]);
  }, []);
  
  const loadMore = useCallback(() => {
    fetchAlerts(true);
  }, [fetchAlerts]);

  // Initial load
  useEffect(() => {
    fetchAlerts(false);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Polling logic
  useEffect(() => {
    if (stopPolling) return;
    
    let intervalId: number | null = null;
    
    const startPolling = () => {
      if (!intervalId) {
        intervalId = window.setInterval(() => {
          if (document.visibilityState === 'visible') {
            fetchAlerts(false);
          }
        }, pollInterval);
      }
    };
    
    const stopPollingInterval = () => {
      if (intervalId) {
        window.clearInterval(intervalId);
        intervalId = null;
      }
    };

    // Initial start if visible
    if (document.visibilityState === 'visible') {
      startPolling();
    }

    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        fetchAlerts(false); // Fetch immediately upon becoming visible
        startPolling();
      } else {
        stopPollingInterval();
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    
    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      stopPollingInterval();
    };
  }, [fetchAlerts, pollInterval, stopPolling]);

  return {
    alerts,
    isLoading,
    error,
    hasAlerts: alerts.length > 0,
    hasMore,
    fetchAlerts: () => fetchAlerts(false),
    loadMore,
    dismissAlert,
    clearAllAlerts
  };
}
