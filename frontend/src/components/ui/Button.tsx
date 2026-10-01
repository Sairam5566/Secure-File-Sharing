import React from 'react';

type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger';
type ButtonSize = 'sm' | 'md' | 'lg';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
  icon?: React.ReactNode;
  iconRight?: React.ReactNode;
  as?: 'button' | 'a';
  href?: string;
}

export function Button({
  variant = 'secondary',
  size = 'md',
  loading = false,
  icon,
  iconRight,
  children,
  disabled,
  className = '',
  ...props
}: ButtonProps) {
  const variantClass = `btn-${variant}`;
  const sizeClass = size !== 'md' ? `btn-${size}` : '';
  const cls = ['btn', variantClass, sizeClass, className].filter(Boolean).join(' ');

  return (
    <button
      className={cls}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...props}
    >
      {loading ? (
        <span className="spinner" aria-hidden="true" style={{ width: '0.875rem', height: '0.875rem' }} />
      ) : icon ? (
        <span aria-hidden="true" style={{ display: 'flex', alignItems: 'center' }}>{icon}</span>
      ) : null}
      {children}
      {iconRight && !loading && (
        <span aria-hidden="true" style={{ display: 'flex', alignItems: 'center' }}>{iconRight}</span>
      )}
    </button>
  );
}
