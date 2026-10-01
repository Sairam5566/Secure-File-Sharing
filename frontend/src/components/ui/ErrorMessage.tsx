import React from 'react';
import { AlertCircle, AlertTriangle, CheckCircle2, Info } from 'lucide-react';

type MessageVariant = 'error' | 'warning' | 'success' | 'info';

interface ErrorMessageProps {
  variant?: MessageVariant;
  children: React.ReactNode;
  className?: string;
  id?: string;
  style?: React.CSSProperties;
}

const ICONS: Record<MessageVariant, React.ReactNode> = {
  error:   <AlertCircle   size={16} strokeWidth={1.75} aria-hidden="true" />,
  warning: <AlertTriangle size={16} strokeWidth={1.75} aria-hidden="true" />,
  success: <CheckCircle2  size={16} strokeWidth={1.75} aria-hidden="true" />,
  info:    <Info          size={16} strokeWidth={1.75} aria-hidden="true" />,
};

export function ErrorMessage({ variant = 'error', children, className = '', id, style }: ErrorMessageProps) {
  const cls = [`message`, `message-${variant}`, className].filter(Boolean).join(' ');
  return (
    <div id={id} className={cls} role={variant === 'error' ? 'alert' : 'status'} style={style}>
      <span style={{ flexShrink: 0, marginTop: '0.1rem' }}>{ICONS[variant]}</span>
      <span>{children}</span>
    </div>
  );
}
