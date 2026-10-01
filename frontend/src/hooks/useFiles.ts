import { useState, useCallback } from 'react';
import { useApi } from './useApi';

export interface FileItem {
  id: number;
  filename: string;
  file_hash: string;
  owner_id: number;
  upload_time: string;
  is_deleted: boolean;
  blockchain_tx_hash?: string;
  blockchain_index?: number;
  is_anomalous?: boolean;
}

export interface AccessLog {
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

export function useFiles() {
  const { request } = useApi();
  const [files, setFiles] = useState<FileItem[]>([]);
  const [accessLogs, setAccessLogs] = useState<AccessLog[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [uploadProgress, setUploadProgress] = useState<number>(0);

  const fetchFiles = useCallback(async (): Promise<void> => {
    setIsLoading(true);
    setError(null);

    try {
      const data = await request<FileItem[]>('/files/', { requiresAuth: true });
      setFiles(data);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to fetch files';
      setError(errorMessage);
    } finally {
      setIsLoading(false);
    }
  }, [request]);

  const fetchAccessLogs = useCallback(async (fileId?: number): Promise<void> => {
    setIsLoading(true);
    setError(null);

    try {
      const params = fileId ? `?file_id=${fileId}` : '';
      const data = await request<AccessLog[]>(`/access-logs/${params}`, { requiresAuth: true });
      setAccessLogs(data);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to fetch access logs';
      setError(errorMessage);
    } finally {
      setIsLoading(false);
    }
  }, [request]);

  const uploadFile = useCallback(async (file: File): Promise<FileItem> => {
    setIsLoading(true);
    setError(null);
    setUploadProgress(0);

    try {
      const formData = new FormData();
      formData.append('file', file);

      const MAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024; // 10 MB
      if (file.size > MAX_UPLOAD_SIZE_BYTES) {
        throw new Error("File is larger than the 10 MB limit.");
      }
      
      const allowedExts = [
        'txt', 'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx',
        'csv', 'json', 'xml',
        'png', 'jpg', 'jpeg', 'gif', 'bmp', 'svg', 'webp',
        'zip', 'tar', 'gz', '7z', 'rar',
        'mp4', 'mp3', 'wav', 'avi', 'mov',
        'py', 'js', 'ts', 'html', 'css', 'md'
      ];
      const ext = file.name.split('.').pop()?.toLowerCase() || '';
      if (!allowedExts.includes(ext)) {
        throw new Error(`File type '.${ext}' is not allowed. Permitted types: ${allowedExts.map(e => '.' + e).sort().join(', ')}`);
      }

      // Simulate progress since fetch doesn't support progress events
      const progressInterval = setInterval(() => {
        setUploadProgress(prev => Math.min(prev + 10, 90));
      }, 200);

      const data = await request<FileItem>('/files/upload', {
        method: 'POST',
        body: formData,
        requiresAuth: true
      });

      clearInterval(progressInterval);
      setUploadProgress(100);

      setFiles(prev => [data, ...prev]);
      return data;
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Upload failed';
      setError(errorMessage);
      throw err;
    } finally {
      setIsLoading(false);
      setTimeout(() => setUploadProgress(0), 1000);
    }
  }, [request]);

  const downloadFile = useCallback(async (fileId: number, filename: string): Promise<void> => {
    setIsLoading(true);
    setError(null);

    try {
      const blob = await request<Blob>(`/files/download/${fileId}`, {
        requiresAuth: true,
        responseType: 'blob'
      });

      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Download failed';
      setError(errorMessage);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, [request]);

  const deleteFile = useCallback(async (fileId: number): Promise<void> => {
    setIsLoading(true);
    setError(null);

    try {
      await request<{ detail: string; file_id: number }>(`/files/${fileId}`, {
        method: 'DELETE',
        requiresAuth: true
      });
      setFiles(prev => prev.filter(f => f.id !== fileId));
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Delete failed';
      setError(errorMessage);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, [request]);

  const verifyFile = useCallback(async (fileId: number): Promise<{
    file_id: number;
    filename: string;
    stored_hash: string;
    current_hash: string | null;
    integrity_ok: boolean;
    tamper_reason?: string;
    blockchain_verified: boolean | null;
    verified_at: string;
  }> => {
    setIsLoading(true);
    setError(null);

    try {
      const data = await request<{
        file_id: number;
        filename: string;
        stored_hash: string;
        current_hash: string | null;
        integrity_ok: boolean;
        tamper_reason?: string;
        blockchain_verified: boolean | null;
        verified_at: string;
      }>(`/files/${fileId}/verify`, { requiresAuth: true });
      
      return data;
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Verification failed';
      setError(errorMessage);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, [request]);

  return {
    files,
    accessLogs,
    isLoading,
    error,
    uploadProgress,
    fetchFiles,
    fetchAccessLogs,
    uploadFile,
    downloadFile,
    deleteFile,
    verifyFile
  };
}
