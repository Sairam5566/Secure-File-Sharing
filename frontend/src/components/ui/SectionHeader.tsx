import React from 'react';

interface SectionHeaderProps {
  label?: string;        // small-caps label above title
  title: string;
  action?: React.ReactNode;  // slot for a button or badge on the right
  className?: string;
}

export function SectionHeader({ label, title, action, className = '' }: SectionHeaderProps) {
  return (
    <div className={`section-header ${className}`}>
      <div>
        {label && <p className="section-label">{label}</p>}
        <h2 className="section-title">{title}</h2>
      </div>
      {action && <div>{action}</div>}
    </div>
  );
}
