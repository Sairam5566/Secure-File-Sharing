import { useState, useEffect } from 'react';
import { useApi } from '../hooks/useApi';
import { SectionHeader } from './ui/SectionHeader';
import { Badge } from './ui/Badge';
import { ErrorMessage } from './ui/ErrorMessage';
import { EmptyState } from './ui/EmptyState';
import { ShieldAlert, CheckCircle2, Shield, FileWarning, SearchX } from 'lucide-react';
import { Button } from './ui/Button';

interface ScanResults {
  total_files_scanned: number;
  valid_files: number;
  tampered_files: any[];
  missing_files: any[];
  not_anchored: any[];
  blockchain_mismatch: any[];
}

interface AnomalyReport {
  total_anomalies: number;
  skip: number;
  limit: number;
  anomalies: any[];
}

export function AdminPanel() {
  const { request } = useApi();
  const [scanResults, setScanResults] = useState<ScanResults | null>(null);
  const [anomalyReport, setAnomalyReport] = useState<AnomalyReport | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchAdminData = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [scan, anomalies] = await Promise.all([
        request<ScanResults>('/admin/scan-integrity', { requiresAuth: true }),
        request<AnomalyReport>('/admin/anomaly-report?limit=50', { requiresAuth: true })
      ]);
      setScanResults(scan);
      setAnomalyReport(anomalies);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to load admin data';
      setError(errorMessage);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchAdminData();
  }, []);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
      <section>
        <SectionHeader 
          label="Administration" 
          title="System Integrity & Anomalies" 
          action={
            <Button variant="secondary" size="sm" onClick={fetchAdminData} disabled={isLoading}>
              Refresh Data
            </Button>
          }
        />
        
        {error && (
          <ErrorMessage style={{ marginBottom: '1rem' }}>
            {error}
          </ErrorMessage>
        )}

        {isLoading && !scanResults ? (
          <EmptyState
            title="Scanning system..."
            icon={<div className="spinner" style={{ width: '2rem', height: '2rem' }} />}
          />
        ) : scanResults && anomalyReport ? (
          <div style={{ display: 'grid', gap: '2rem' }}>
            {/* Integrity Summary */}
            <div style={{ 
              backgroundColor: 'var(--color-surface)', 
              border: '1px solid var(--color-border)',
              padding: '1.5rem',
              display: 'flex',
              flexDirection: 'column',
              gap: '1.5rem'
            }}>
              <div>
                <h3 style={{ fontFamily: 'var(--font-heading)', fontSize: '1.125rem', fontWeight: 600, color: 'var(--color-ink)', marginBottom: '0.25rem' }}>
                  Integrity Scan Results
                </h3>
                <p style={{ fontSize: '0.8125rem', color: 'var(--color-muted)' }}>
                  Scanned {scanResults.total_files_scanned} total files.
                </p>
              </div>

              <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', backgroundColor: 'var(--color-parchment)', padding: '0.75rem 1rem', border: '1px solid var(--color-border)' }}>
                  <CheckCircle2 size={16} color="var(--color-intact)" />
                  <div>
                    <div style={{ fontSize: '0.75rem', textTransform: 'uppercase', color: 'var(--color-muted)', fontWeight: 600 }}>Valid Files</div>
                    <div style={{ fontSize: '1.25rem', fontWeight: 600, color: 'var(--color-ink)' }}>{scanResults.valid_files}</div>
                  </div>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', backgroundColor: 'var(--color-parchment)', padding: '0.75rem 1rem', border: '1px solid var(--color-border)' }}>
                  <ShieldAlert size={16} color="var(--color-danger)" />
                  <div>
                    <div style={{ fontSize: '0.75rem', textTransform: 'uppercase', color: 'var(--color-muted)', fontWeight: 600 }}>Tampered</div>
                    <div style={{ fontSize: '1.25rem', fontWeight: 600, color: 'var(--color-ink)' }}>{scanResults.tampered_files.length}</div>
                  </div>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', backgroundColor: 'var(--color-parchment)', padding: '0.75rem 1rem', border: '1px solid var(--color-border)' }}>
                  <SearchX size={16} color="var(--color-caution)" />
                  <div>
                    <div style={{ fontSize: '0.75rem', textTransform: 'uppercase', color: 'var(--color-muted)', fontWeight: 600 }}>Missing</div>
                    <div style={{ fontSize: '1.25rem', fontWeight: 600, color: 'var(--color-ink)' }}>{scanResults.missing_files.length}</div>
                  </div>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', backgroundColor: 'var(--color-parchment)', padding: '0.75rem 1rem', border: '1px solid var(--color-border)' }}>
                  <Shield size={16} color="var(--color-caution)" />
                  <div>
                    <div style={{ fontSize: '0.75rem', textTransform: 'uppercase', color: 'var(--color-muted)', fontWeight: 600 }}>Not Anchored</div>
                    <div style={{ fontSize: '1.25rem', fontWeight: 600, color: 'var(--color-ink)' }}>{scanResults.not_anchored.length}</div>
                  </div>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', backgroundColor: 'var(--color-parchment)', padding: '0.75rem 1rem', border: '1px solid var(--color-border)' }}>
                  <FileWarning size={16} color="var(--color-danger)" />
                  <div>
                    <div style={{ fontSize: '0.75rem', textTransform: 'uppercase', color: 'var(--color-muted)', fontWeight: 600 }}>Blockchain Mismatch</div>
                    <div style={{ fontSize: '1.25rem', fontWeight: 600, color: 'var(--color-ink)' }}>{scanResults.blockchain_mismatch.length}</div>
                  </div>
                </div>
              </div>

              {/* Detailed Lists */}
              {scanResults.tampered_files.length > 0 && (
                <div style={{ marginTop: '1rem' }}>
                  <h4 style={{ fontSize: '0.875rem', fontWeight: 600, color: 'var(--color-danger)', marginBottom: '0.5rem' }}>Tampered Files</h4>
                  <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                    {scanResults.tampered_files.map((file, i) => (
                      <li key={i} style={{ fontSize: '0.8125rem', padding: '0.5rem', backgroundColor: 'var(--color-parchment)', border: '1px solid var(--color-border)' }}>
                        <span style={{ fontWeight: 600, color: 'var(--color-ink)' }}>{file.filename}</span> (ID: {file.file_id})
                        <div style={{ color: 'var(--color-danger)', marginTop: '0.25rem' }}>{file.reason}</div>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>

            {/* Anomaly Report */}
            <div style={{ 
              backgroundColor: 'var(--color-surface)', 
              border: '1px solid var(--color-border)',
              padding: '1.5rem',
            }}>
              <div style={{ marginBottom: '1.5rem' }}>
                <h3 style={{ fontFamily: 'var(--font-heading)', fontSize: '1.125rem', fontWeight: 600, color: 'var(--color-ink)', marginBottom: '0.25rem' }}>
                  Anomaly Report
                </h3>
                <p style={{ fontSize: '0.8125rem', color: 'var(--color-muted)' }}>
                  Total anomalies detected: {anomalyReport.total_anomalies}
                </p>
              </div>

              {anomalyReport.anomalies.length === 0 ? (
                <div style={{ padding: '2rem', textAlign: 'center', backgroundColor: 'var(--color-parchment)', border: '1px dashed var(--color-border)' }}>
                  <p style={{ fontSize: '0.875rem', color: 'var(--color-muted)' }}>No anomalous events recorded.</p>
                </div>
              ) : (
                <div style={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.875rem' }}>
                    <thead>
                      <tr style={{ borderBottom: '1px solid var(--color-border)' }}>
                        <th style={{ padding: '0.75rem 1rem', fontWeight: 600, color: 'var(--color-ink)', backgroundColor: 'var(--color-parchment)' }}>Time</th>
                        <th style={{ padding: '0.75rem 1rem', fontWeight: 600, color: 'var(--color-ink)', backgroundColor: 'var(--color-parchment)' }}>User ID</th>
                        <th style={{ padding: '0.75rem 1rem', fontWeight: 600, color: 'var(--color-ink)', backgroundColor: 'var(--color-parchment)' }}>Action</th>
                        <th style={{ padding: '0.75rem 1rem', fontWeight: 600, color: 'var(--color-ink)', backgroundColor: 'var(--color-parchment)' }}>Detection</th>
                        <th style={{ padding: '0.75rem 1rem', fontWeight: 600, color: 'var(--color-ink)', backgroundColor: 'var(--color-parchment)' }}>Score</th>
                      </tr>
                    </thead>
                    <tbody>
                      {anomalyReport.anomalies.map((anomaly) => (
                        <tr key={anomaly.id} style={{ borderBottom: '1px solid var(--color-rule)' }}>
                          <td style={{ padding: '0.75rem 1rem', color: 'var(--color-muted)' }}>
                            {new Date(anomaly.timestamp).toLocaleString()}
                          </td>
                          <td style={{ padding: '0.75rem 1rem', color: 'var(--color-ink)' }}>{anomaly.user_id}</td>
                          <td style={{ padding: '0.75rem 1rem' }}>
                            <span style={{ textTransform: 'capitalize', fontWeight: 500, color: 'var(--color-ink)' }}>{anomaly.action_type}</span>
                            <span style={{ marginLeft: '0.5rem', color: anomaly.access_status === 'granted' ? 'var(--color-intact)' : 'var(--color-danger)' }}>
                              ({anomaly.access_status})
                            </span>
                          </td>
                          <td style={{ padding: '0.75rem 1rem' }}>
                            <Badge variant="neutral">{anomaly.detection === 'model' ? 'Model' : 'Rule-based'}</Badge>
                          </td>
                          <td style={{ padding: '0.75rem 1rem', fontFamily: 'monospace', color: 'var(--color-ink)' }}>
                            {anomaly.anomaly_score !== null ? anomaly.anomaly_score.toFixed(3) : '-'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        ) : null}
      </section>
    </div>
  );
}
