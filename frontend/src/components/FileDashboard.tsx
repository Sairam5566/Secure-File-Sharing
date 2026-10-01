import { useState, useEffect, useCallback, useRef } from 'react';
import { useFiles, type FileItem } from '../hooks/useFiles';
import { SectionHeader } from './ui/SectionHeader';
import { DataTable, type Column } from './ui/DataTable';
import { Badge } from './ui/Badge';
import { Button } from './ui/Button';
import { ErrorMessage } from './ui/ErrorMessage';
import { EmptyState } from './ui/EmptyState';
import { Upload, Download, Trash2, Shield, ShieldAlert, ShieldCheck, X, FileText, Link as LinkIcon, Copy } from 'lucide-react';

interface FileDashboardProps {
  onLogout: () => void;
}

export function FileDashboard({ onLogout: _onLogout }: FileDashboardProps) {
  const {
    files,
    isLoading,
    error,
    uploadProgress,
    fetchFiles,
    uploadFile,
    downloadFile,
    deleteFile,
    verifyFile
  } = useFiles();

  const [verifyingFile, setVerifyingFile] = useState<number | null>(null);
  const [fileIntegrity, setFileIntegrity] = useState<Record<number, boolean>>({});
  const [verificationResult, setVerificationResult] = useState<{
    file_id: number;
    filename: string;
    stored_hash: string;
    current_hash: string | null;
    integrity_ok: boolean;
    tamper_reason?: string;
    blockchain_verified: boolean | null;
    verified_at: string;
    blockchain_tx_hash: string | null;
  } | null>(null);

  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const triggerButtonRef = useRef<HTMLButtonElement | null>(null);

  useEffect(() => {
    fetchFiles();
  }, [fetchFiles]);

  const handleFileUpload = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      await uploadFile(file);
    } catch {}
  }, [uploadFile]);

  const handleDownload = useCallback(async (file: FileItem) => {
    try {
      await downloadFile(file.id, file.filename);
    } catch {}
  }, [downloadFile]);

  const handleDelete = useCallback(async (fileId: number) => {
    if (!confirm('Are you sure you want to delete this file?')) return;
    try {
      await deleteFile(fileId);
    } catch {}
  }, [deleteFile]);

  const handleVerify = useCallback(async (fileId: number, e: React.MouseEvent<HTMLButtonElement>) => {
    triggerButtonRef.current = e.currentTarget;
    setVerifyingFile(fileId);
    setVerificationResult(null);
    try {
      const result = await verifyFile(fileId);
      const file = files.find(f => f.id === fileId);
      
      setFileIntegrity(prev => ({ ...prev, [fileId]: result.integrity_ok }));
      setVerificationResult({
        ...result,
        blockchain_tx_hash: file?.blockchain_tx_hash || null
      });
    } catch {}
    finally {
      setVerifyingFile(null);
    }
  }, [verifyFile, files]);

  const closeVerification = useCallback(() => {
    setVerificationResult(null);
    if (triggerButtonRef.current) {
      triggerButtonRef.current.focus();
    }
  }, []);

  useEffect(() => {
    if (verificationResult) {
      closeButtonRef.current?.focus();
      
      const handleKeyDown = (e: KeyboardEvent) => {
        if (e.key === 'Escape') {
          closeVerification();
        }
      };
      document.addEventListener('keydown', handleKeyDown);
      return () => document.removeEventListener('keydown', handleKeyDown);
    }
  }, [verificationResult, closeVerification]);

  const columns: Column<FileItem>[] = [
    {
      key: 'filename',
      label: 'File Name',
      render: (file) => (
        <span style={{ fontWeight: 500, color: 'var(--color-ink)' }}>{file.filename}</span>
      )
    },
    {
      key: 'upload_time',
      label: 'Uploaded',
      render: (file) => (
        <span style={{ color: 'var(--color-muted)' }}>{new Date(file.upload_time).toLocaleString()}</span>
      )
    },
    {
      key: 'status',
      label: 'Blockchain',
      render: (file) => (
        <div style={{ display: 'flex', gap: '0.375rem', flexWrap: 'wrap' }}>
          {file.blockchain_tx_hash ? (
            <Badge variant="intact">Anchored</Badge>
          ) : (
            <Badge variant="neutral">Pending</Badge>
          )}
        </div>
      )
    },
    {
      key: 'integrity',
      label: 'Integrity',
      render: (file) => {
        const ok = fileIntegrity[file.id];
        if (ok === true) return <Badge variant="intact">Intact</Badge>;
        if (ok === false) return <Badge variant="danger">Tampered</Badge>;
        return <Badge variant="neutral">Not checked</Badge>;
      }
    },
    {
      key: 'actions',
      label: 'Actions',
      render: (file) => (
        <div style={{ display: 'flex', gap: '0.25rem' }}>
          <Button
            variant="ghost"
            size="sm"
            onClick={(e) => handleVerify(file.id, e)}
            loading={verifyingFile === file.id}
            icon={<Shield size={14} />}
            title="Verify integrity"
          />
          <Button
            variant="ghost"
            size="sm"
            onClick={() => handleDownload(file)}
            icon={<Download size={14} />}
            title="Download"
          />
          <Button
            variant="ghost"
            size="sm"
            onClick={() => handleDelete(file.id)}
            icon={<Trash2 size={14} />}
            title="Delete"
          />
        </div>
      )
    }
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
      
      {/* Upload Zone */}
      <section>
        <SectionHeader 
          label="Upload" 
          title="Secure File Upload" 
        />
        <div style={{ position: 'relative' }}>
          <input
            type="file"
            onChange={handleFileUpload}
            id="file-upload"
            disabled={isLoading}
            style={{
              position: 'absolute',
              width: '100%',
              height: '100%',
              opacity: 0,
              cursor: 'pointer',
              zIndex: 10
            }}
          />
          <div className="drop-zone">
            <Upload size={32} style={{ margin: '0 auto 1rem auto', color: 'var(--color-pine)' }} />
            <p style={{ fontWeight: 600, color: 'var(--color-ink)', marginBottom: '0.25rem' }}>Select a file to encrypt & upload</p>
            <p style={{ fontSize: '0.8125rem', color: 'var(--color-muted)' }}>Files are AES-128 encrypted and hashed before anchoring to the blockchain.</p>
          </div>
          
          {uploadProgress > 0 && (
            <div style={{ marginTop: '1rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8125rem', marginBottom: '0.25rem' }}>
                <span style={{ color: 'var(--color-muted)' }}>Uploading...</span>
                <span style={{ fontWeight: 600 }}>{uploadProgress}%</span>
              </div>
              <div className="progress-track">
                <div className="progress-bar" style={{ width: `${uploadProgress}%` }} />
              </div>
            </div>
          )}
        </div>
      </section>

      {/* Files Table */}
      <section>
        <SectionHeader 
          label="Archive" 
          title="Your Files" 
          action={
            <Button variant="secondary" size="sm" onClick={fetchFiles} disabled={isLoading}>
              Refresh
            </Button>
          }
        />
        
        {error && (
          <ErrorMessage style={{ marginBottom: '1rem' }}>
            {error}
          </ErrorMessage>
        )}

        {isLoading && files.length === 0 ? (
          <EmptyState
            title="Loading files..."
            icon={<div className="spinner" style={{ width: '2rem', height: '2rem' }} />}
          />
        ) : files.length === 0 ? (
          <EmptyState
            title="No files yet."
            description="Upload your first file."
          />
        ) : (
          <DataTable
            rows={files}
            columns={columns}
            keyField="id"
          />
        )}
      </section>

      {/* Verification Modal - Receipt View */}
      {verificationResult && (
        <div 
          role="dialog"
          aria-modal="true"
          aria-labelledby="receipt-title"
          style={{
            position: 'fixed', inset: 0, zIndex: 100,
            backgroundColor: 'rgba(28, 36, 48, 0.4)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '1rem',
            overflowY: 'auto'
          }}
          onClick={(e) => {
            if (e.target === e.currentTarget) closeVerification();
          }}
        >
          <div 
            style={{ 
              width: '100%', 
              maxWidth: '36rem', 
              position: 'relative',
              backgroundColor: 'var(--color-parchment)',
              border: '1px solid var(--color-border)',
              padding: '1.5rem',
              margin: 'auto'
            }}
          >
            <div style={{ border: '1px solid var(--color-border)', padding: '1.5rem', backgroundColor: 'var(--color-surface)', position: 'relative' }}>
              <button
                ref={closeButtonRef}
                onClick={closeVerification}
                aria-label="Close"
                style={{ position: 'absolute', top: '1rem', right: '1rem', background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-muted)', padding: '0.5rem' }}
              >
                <X size={18} />
              </button>

              <div style={{ textAlign: 'center', marginBottom: '1.5rem' }}>
                <div style={{ display: 'inline-flex', justifyContent: 'center', alignItems: 'center', width: '3rem', height: '3rem', borderRadius: '50%', backgroundColor: verificationResult.integrity_ok ? 'var(--color-parchment)' : 'var(--color-danger)', border: `1px solid ${verificationResult.integrity_ok ? 'var(--color-border)' : 'var(--color-danger)'}`, color: verificationResult.integrity_ok ? 'var(--color-intact)' : 'white', marginBottom: '1rem' }}>
                  {verificationResult.integrity_ok ? <ShieldCheck size={24} /> : <ShieldAlert size={24} />}
                </div>
                <h3 id="receipt-title" style={{ fontFamily: 'var(--font-heading)', fontSize: '1.5rem', fontWeight: 600, color: 'var(--color-ink)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '0.25rem' }}>
                  Verification Receipt
                </h3>
                <p style={{ fontSize: '0.8125rem', color: 'var(--color-muted)' }}>
                  {new Date(verificationResult.verified_at).toLocaleString()}
                </p>
              </div>

              {/* Status Badges */}
              <div style={{ display: 'flex', justifyContent: 'center', gap: '0.5rem', marginBottom: '1.5rem', flexWrap: 'wrap' }}>
                <Badge variant={verificationResult.integrity_ok ? 'intact' : 'danger'}>
                  {verificationResult.integrity_ok ? 'Integrity Intact' : 'Integrity Compromised'}
                </Badge>
                
                <Badge variant={verificationResult.blockchain_verified === true ? 'intact' : (verificationResult.blockchain_verified === false ? 'danger' : 'neutral')}>
                  {verificationResult.blockchain_verified === true ? 'Matches chain' : (verificationResult.blockchain_verified === false ? 'Does not match chain' : 'Not recorded')}
                </Badge>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem', borderTop: '1px dashed var(--color-border)', borderBottom: '1px dashed var(--color-border)', padding: '1.25rem 0' }}>
                
                <div>
                  <div style={{ fontSize: '0.75rem', textTransform: 'uppercase', color: 'var(--color-muted)', fontWeight: 600, marginBottom: '0.25rem' }}>File Identity</div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--color-ink)' }}>
                    <FileText size={16} style={{ flexShrink: 0 }} />
                    <span style={{ fontWeight: 500, wordBreak: 'break-word' }}>{verificationResult.filename}</span>
                  </div>
                </div>

                <div>
                  <div style={{ fontSize: '0.75rem', textTransform: 'uppercase', color: 'var(--color-muted)', fontWeight: 600, marginBottom: '0.25rem' }}>Expected Hash (Database)</div>
                  <div style={{ fontFamily: 'monospace', fontSize: '0.875rem', color: 'var(--color-ink)', backgroundColor: 'var(--color-parchment)', padding: '0.5rem', border: '1px solid var(--color-border)', wordBreak: 'break-all' }}>
                    {verificationResult.stored_hash}
                  </div>
                </div>

                <div>
                  <div style={{ fontSize: '0.75rem', textTransform: 'uppercase', color: 'var(--color-muted)', fontWeight: 600, marginBottom: '0.25rem' }}>Actual Hash (Computed)</div>
                  <div style={{ fontFamily: 'monospace', fontSize: '0.875rem', color: verificationResult.integrity_ok ? 'var(--color-ink)' : 'var(--color-danger)', backgroundColor: 'var(--color-parchment)', padding: '0.5rem', border: '1px solid var(--color-border)', wordBreak: 'break-all' }}>
                    {verificationResult.current_hash ? verificationResult.current_hash : 'Could not be computed (file failed decryption)'}
                  </div>
                </div>

              </div>
              
              <div style={{ marginTop: '1.5rem', textAlign: 'center' }}>
                <p style={{ fontWeight: 600, color: verificationResult.integrity_ok ? 'var(--color-intact)' : 'var(--color-danger)', fontSize: '1.125rem', marginBottom: '0.5rem', letterSpacing: '0.025em' }}>
                  {verificationResult.integrity_ok ? '✓ INTEGRITY VERIFIED' : '✗ INTEGRITY COMPROMISED'}
                </p>
                <p style={{ fontSize: '0.875rem', color: 'var(--color-muted)' }}>
                  {verificationResult.integrity_ok ? 'The file has not been altered since it was uploaded.' : verificationResult.tamper_reason}
                </p>

                <div style={{ marginTop: '1rem', paddingTop: '1rem', borderTop: '1px solid var(--color-border)', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem' }}>
                  {verificationResult.blockchain_tx_hash ? (
                    <>
                      <LinkIcon size={14} color="var(--color-ink)" />
                      <span style={{ fontSize: '0.8125rem', color: 'var(--color-ink)' }}>
                        Hash recorded on Sepolia testnet: <span style={{ fontFamily: 'monospace' }}>{verificationResult.blockchain_tx_hash.slice(0, 10)}...{verificationResult.blockchain_tx_hash.slice(-8)}</span>
                      </span>
                      <Button 
                        variant="ghost" 
                        size="sm" 
                        icon={<Copy size={12} />} 
                        onClick={() => navigator.clipboard.writeText(verificationResult.blockchain_tx_hash!)}
                        title="Copy Transaction Hash"
                      />
                    </>
                  ) : (
                    <span style={{ fontSize: '0.8125rem', color: 'var(--color-muted)' }}>
                      Not recorded on blockchain
                    </span>
                  )}
                </div>
              </div>

            </div>
          </div>
        </div>
      )}
    </div>
  );
}
