import React from 'react';

type BadgeVariant = 'intact' | 'caution' | 'danger' | 'neutral' | 'brass';

interface BadgeProps {
  variant?: BadgeVariant;
  icon?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}

export function Badge({ variant = 'neutral', icon, children, className = '' }: BadgeProps) {
  const cls = ['badge', `badge-${variant}`, className].filter(Boolean).join(' ');
  return (
    <span className={cls}>
      {icon && <span aria-hidden="true" style={{ display: 'flex', alignItems: 'center' }}>{icon}</span>}
      {children}
    </span>
  );
}
