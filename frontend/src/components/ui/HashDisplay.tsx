import { useState, useCallback } from 'react';
import { Copy, Check } from 'lucide-react';

interface HashDisplayProps {
  hash: string;
  /** Characters to keep at start (default 8) */
  prefixLen?: number;
  /** Characters to keep at end (default 6) */
  suffixLen?: number;
  /** Show full hash on hover/click, default false */
  expandable?: boolean;
  className?: string;
}

function truncateHash(hash: string, prefix: number, suffix: number): string {
  if (hash.length <= prefix + suffix + 3) return hash;
  return `${hash.slice(0, prefix)}…${hash.slice(-suffix)}`;
}

export function HashDisplay({
  hash,
  prefixLen = 8,
  suffixLen = 6,
  expandable = false,
  className = '',
}: HashDisplayProps) {
  const [copied, setCopied] = useState(false);
  const [expanded, setExpanded] = useState(false);

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(hash);
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch {
      // Clipboard not available in some contexts
    }
  }, [hash]);

  const displayHash = expanded ? hash : truncateHash(hash, prefixLen, suffixLen);

  return (
    <span className={`hash-display ${className}`}>
      {expandable ? (
        <button
          type="button"
          onClick={() => setExpanded(e => !e)}
          title={expanded ? 'Collapse' : 'Show full hash'}
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 'inherit',
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            color: 'inherit',
            padding: 0,
          }}
        >
          {displayHash}
        </button>
      ) : (
        <span title={hash}>{displayHash}</span>
      )}
      <button
        type="button"
        className="hash-copy-btn"
        onClick={handleCopy}
        aria-label={copied ? 'Copied' : 'Copy hash'}
        title={copied ? 'Copied!' : 'Copy to clipboard'}
      >
        {copied
          ? <Check size={13} strokeWidth={2.5} aria-hidden="true" />
          : <Copy size={13} strokeWidth={1.75} aria-hidden="true" />
        }
      </button>
    </span>
  );
}
