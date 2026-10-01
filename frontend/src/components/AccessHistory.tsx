import { useEffect } from 'react';
import { useFiles } from '../hooks/useFiles';
import { SectionHeader } from './ui/SectionHeader';
import { DataTable, type Column } from './ui/DataTable';
import { Badge } from './ui/Badge';
import { ErrorMessage } from './ui/ErrorMessage';
import { EmptyState } from './ui/EmptyState';
import { Clock, Upload, Download, Trash2 } from 'lucide-react';
import type { AccessLog } from '../hooks/useFiles';

export function AccessHistory() {
  const { accessLogs, isLoading, error, fetchAccessLogs } = useFiles();

  useEffect(() => {
    fetchAccessLogs();
  }, [fetchAccessLogs]);

  const getActionIcon = (actionType: string) => {
    switch (actionType) {
      case 'upload':
        return <Upload size={14} style={{ marginRight: '0.25rem' }} />;
      case 'download':
        return <Download size={14} style={{ marginRight: '0.25rem' }} />;
      case 'delete':
        return <Trash2 size={14} style={{ marginRight: '0.25rem' }} />;
      default:
        return <Clock size={14} style={{ marginRight: '0.25rem' }} />;
    }
  };

  const columns: Column<AccessLog>[] = [
    {
      key: 'action_type',
      label: 'Action',
      render: (log) => (
        <span style={{ display: 'flex', alignItems: 'center', fontWeight: 500, textTransform: 'capitalize' }}>
          {getActionIcon(log.action_type)}
          {log.action_type}
        </span>
      )
    },
    {
      key: 'access_time',
      label: 'Time',
      render: (log) => (
        <span style={{ color: 'var(--color-muted)' }}>{new Date(log.access_time).toLocaleString()}</span>
      )
    },
    {
      key: 'status',
      label: 'Status',
      render: (log) => {
        let variant: 'intact' | 'danger' | 'caution' | 'neutral' = 'neutral';
        let label = log.access_status;
        
        if (log.access_status === 'success' || log.access_status === 'granted') {
          variant = 'intact';
          label = 'Granted';
        } else if (log.access_status === 'denied') {
          variant = 'danger';
          label = 'Denied';
        }

        return (
          <div style={{ display: 'flex', gap: '0.375rem', flexWrap: 'wrap' }}>
            <Badge variant={variant}>{label}</Badge>
            {log.is_anomalous && (
              <Badge variant="caution">Flagged</Badge>
            )}
          </div>
        );
      }
    },
    {
      key: 'details',
      label: 'Client Details',
      render: (log) => (
        <div style={{ fontSize: '0.75rem', color: 'var(--color-muted)', lineHeight: 1.4 }}>
          {log.ip_address && <div>IP: {log.ip_address}</div>}
          {log.device_info && <div>Device: {log.device_info}</div>}
        </div>
      )
    }
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
      <section>
        <SectionHeader 
          label="Audit Trail" 
          title="Access History" 
        />
        
        {error && (
          <ErrorMessage variant="error" style={{ marginBottom: '1rem' }}>
            {error}
          </ErrorMessage>
        )}

        {isLoading && accessLogs.length === 0 ? (
          <EmptyState
            title="Loading logs..."
            icon={<div className="spinner" style={{ width: '2rem', height: '2rem' }} />}
          />
        ) : accessLogs.length === 0 ? (
          <EmptyState
            title="No access history"
            description="Your file activity will appear here."
            icon={<Clock size={32} />}
          />
        ) : (
          <DataTable
            rows={accessLogs}
            columns={columns}
            keyField="id"
          />
        )}
      </section>
    </div>
  );
}
