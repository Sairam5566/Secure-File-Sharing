import { useAlerts } from '../hooks/useAlerts';
import { SectionHeader } from './ui/SectionHeader';
import { Button } from './ui/Button';
import { Badge } from './ui/Badge';
import { EmptyState } from './ui/EmptyState';
import { ShieldAlert, Bell, Trash2 } from 'lucide-react';
import { ErrorMessage } from './ui/ErrorMessage';

interface SecurityAlertsProps {
  user?: { id: number; username: string; role: string; email: string; created_at: string };
}

export function SecurityAlerts({ user: _user }: SecurityAlertsProps = {}) {
  const {
    alerts,
    isLoading,
    error,
    hasAlerts,
    hasMore,
    fetchAlerts,
    loadMore,
    dismissAlert,
    clearAllAlerts
  } = useAlerts();

  if (!hasAlerts && !isLoading && !error) {
    return (
      <section>
        <SectionHeader 
          label="Monitoring" 
          title="Security Alerts" 
          action={
            <Button variant="secondary" size="sm" onClick={fetchAlerts} disabled={isLoading}>
              Refresh
            </Button>
          }
        />
        <EmptyState
          title="No Active Threats"
          description="Your file sharing environment is secure. We are monitoring for suspicious activity."
          icon={<Bell size={32} />}
        />
      </section>
    );
  }

  return (
    <section>
      <SectionHeader 
        label="Monitoring" 
        title="Security Alerts" 
        action={
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            {hasAlerts && (
              <Button variant="ghost" size="sm" onClick={clearAllAlerts} icon={<Trash2 size={14} />}>
                Clear All
              </Button>
            )}
            <Button variant="secondary" size="sm" onClick={fetchAlerts} disabled={isLoading}>
              Refresh
            </Button>
          </div>
        }
      />
      
      {error && (
        <ErrorMessage style={{ marginBottom: '1rem' }}>
          {error}
        </ErrorMessage>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        {alerts.map((alert) => {
          const isModel = alert.details?.anomaly_score != null;
          
          return (
            <div key={alert.id} className="panel" style={{ padding: '1.25rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div style={{ display: 'flex', gap: '1rem', alignItems: 'flex-start', flex: 1 }}>
                  <div style={{ marginTop: '0.125rem' }}>
                    <ShieldAlert size={20} color="var(--color-danger)" />
                  </div>
                  <div style={{ flex: 1 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.25rem', flexWrap: 'wrap' }}>
                      <p style={{ fontWeight: 600, color: 'var(--color-ink)' }}>{alert.message}</p>
                      <Badge variant="neutral">
                        {isModel ? 'Model' : 'Rule-based'}
                      </Badge>
                    </div>
                    
                    <p style={{ fontSize: '0.8125rem', color: 'var(--color-muted)', marginBottom: '0.5rem' }}>
                      {new Date(alert.timestamp).toLocaleString()}
                      {isModel && ` • Score: ${alert.details?.anomaly_score}`}
                      {alert.details?.ip_address && ` • IP: ${alert.details.ip_address}`}
                      {alert.details?.device_info && ` • Device: ${alert.details.device_info}`}
                    </p>

                    {isModel && (
                      <p style={{ fontSize: '0.8125rem', color: 'var(--color-ink)', fontStyle: 'italic', paddingLeft: '0.5rem', borderLeft: '2px solid var(--color-border)' }}>
                        Flagged by the model. A higher score means more unusual. Alerts are recorded for review; nothing is blocked.
                      </p>
                    )}
                  </div>
                </div>
                
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => dismissAlert(alert.id)}
                  title="Dismiss Alert"
                  style={{ marginLeft: '1rem' }}
                >
                  Dismiss
                </Button>
              </div>
            </div>
          );
        })}

        {hasMore && (
          <div style={{ display: 'flex', justifyContent: 'center', marginTop: '1rem' }}>
            <Button variant="secondary" onClick={loadMore} disabled={isLoading}>
              {isLoading ? 'Loading...' : 'Load More'}
            </Button>
          </div>
        )}
      </div>
    </section>
  );
}
