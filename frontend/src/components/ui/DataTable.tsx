import React from 'react';

export interface Column<T> {
  key: string;
  label: string;
  render?: (row: T) => React.ReactNode;
  className?: string;
}

interface DataTableProps<T extends { id: number | string }> {
  columns: Column<T>[];
  rows: T[];
  keyField?: keyof T;
  stackable?: boolean;
  className?: string;
  emptyMessage?: string;
}

export function DataTable<T extends { id: number | string }>({
  columns,
  rows,
  keyField = 'id',
  stackable = true,
  className = '',
  emptyMessage = 'No records found.',
}: DataTableProps<T>) {
  const wrapperCls = ['data-table-wrapper', className].filter(Boolean).join(' ');
  const tableCls = ['data-table', stackable ? 'data-table-stackable' : ''].filter(Boolean).join(' ');

  if (rows.length === 0) {
    return (
      <div className={wrapperCls} style={{ padding: '2rem', textAlign: 'center' }}>
        <p style={{ color: 'var(--color-muted)', fontSize: '0.875rem' }}>{emptyMessage}</p>
      </div>
    );
  }

  return (
    <div className={wrapperCls}>
      <table className={tableCls} role="table">
        <thead>
          <tr>
            {columns.map(col => (
              <th key={col.key} className={col.className} scope="col">
                {col.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map(row => (
            <tr key={String(row[keyField])}>
              {columns.map(col => (
                <td key={col.key} data-label={col.label} className={col.className}>
                  {col.render ? col.render(row) : String((row as Record<string, unknown>)[col.key] ?? '—')}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
