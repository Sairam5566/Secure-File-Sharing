import React from 'react';

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  hint?: string;
  error?: string;
  required?: boolean;
  id: string;
}

export function Input({
  label,
  hint,
  error,
  required,
  id,
  className = '',
  ...props
}: InputProps) {
  const inputCls = ['input', error ? 'input-error' : '', className].filter(Boolean).join(' ');

  return (
    <div className="field">
      {label && (
        <label htmlFor={id} className={`field-label${required ? ' field-label-required' : ''}`}>
          {label}
        </label>
      )}
      <input
        id={id}
        className={inputCls}
        aria-describedby={
          [hint ? `${id}-hint` : '', error ? `${id}-error` : ''].filter(Boolean).join(' ') || undefined
        }
        aria-invalid={error ? 'true' : undefined}
        required={required}
        {...props}
      />
      {hint && !error && (
        <p id={`${id}-hint`} className="field-hint">{hint}</p>
      )}
      {error && (
        <p id={`${id}-error`} className="field-error" role="alert">{error}</p>
      )}
    </div>
  );
}
