import { useState } from 'react';
import type { Theme } from '../../theme';

interface Props {
  theme: Theme;
  label: string;
  confirmLabel?: string;
  onConfirm: () => void;
  disabled?: boolean;
}

/** A delete action that requires an explicit confirm step first (issue #30
 * Story 13/14: "with a confirmation step first"). Click once to arm it,
 * click again to actually delete, or click away/Cancel to back out - never
 * a single click that deletes immediately. */
export function ConfirmDeleteButton({ theme, label, confirmLabel = 'Really delete?', onConfirm, disabled }: Props) {
  const [armed, setArmed] = useState(false);

  if (!armed) {
    return (
      <button
        type="button"
        disabled={disabled}
        onClick={() => setArmed(true)}
        style={{
          height: 38,
          padding: '0 14px',
          borderRadius: 999,
          border: '1.5px solid #a8402f',
          background: 'transparent',
          color: '#a8402f',
          fontWeight: 600,
          fontSize: '0.85rem',
          cursor: disabled ? 'default' : 'pointer',
          opacity: disabled ? 0.5 : 1,
        }}
      >
        {label}
      </button>
    );
  }

  return (
    <span style={{ display: 'inline-flex', gap: 8, alignItems: 'center' }}>
      <span style={{ fontSize: '0.8rem', color: theme.text2 }}>{confirmLabel}</span>
      <button
        type="button"
        onClick={() => {
          setArmed(false);
          onConfirm();
        }}
        style={{
          height: 34,
          padding: '0 12px',
          borderRadius: 999,
          border: 'none',
          background: '#a8402f',
          color: '#fff',
          fontWeight: 700,
          fontSize: '0.8rem',
          cursor: 'pointer',
        }}
      >
        Yes, delete
      </button>
      <button
        type="button"
        onClick={() => setArmed(false)}
        style={{
          height: 34,
          padding: '0 12px',
          borderRadius: 999,
          border: `1.5px solid ${theme.border}`,
          background: 'transparent',
          color: theme.text,
          fontWeight: 600,
          fontSize: '0.8rem',
          cursor: 'pointer',
        }}
      >
        Cancel
      </button>
    </span>
  );
}
