import { useId } from 'react';
import type { CSSProperties } from 'react';
import type { Theme } from '../../theme';

const inputStyle = (theme: Theme, hasError: boolean): CSSProperties => ({
  height: 50,
  padding: '0 14px',
  borderRadius: 12,
  border: `1.5px solid ${hasError ? '#a8402f' : theme.border}`,
  background: theme.surfaceSunken,
  color: theme.text,
  fontSize: '1rem',
  width: '100%',
  boxSizing: 'border-box',
});

const labelStyle = (theme: Theme): CSSProperties => ({
  fontWeight: 600,
  fontSize: '0.85rem',
  color: theme.text2,
});

const wrapStyle: CSSProperties = { display: 'flex', flexDirection: 'column', gap: 6 };

interface BaseProps {
  theme: Theme;
  label: string;
  error?: string | null;
  placeholder?: string;
  required?: boolean;
}

interface TextFieldProps extends BaseProps {
  type?: 'text' | 'email' | 'password';
  value: string;
  onChange: (value: string) => void;
  autoComplete?: string;
}

/** Labeled text/email/password input - extracted from the calculator's
 * repeated inline-style pattern (issue #30 Implementation Decisions), reusing
 * `theme.ts`'s tokens rather than introducing a new design system. */
export function TextField({
  theme,
  label,
  value,
  onChange,
  error,
  placeholder,
  type = 'text',
  autoComplete,
  required,
}: TextFieldProps) {
  const id = useId();
  return (
    <div style={wrapStyle}>
      <label htmlFor={id} style={labelStyle(theme)}>{label}</label>
      <input
        id={id}
        type={type}
        value={value}
        placeholder={placeholder}
        autoComplete={autoComplete}
        required={required}
        onChange={(e) => onChange(e.target.value)}
        style={inputStyle(theme, Boolean(error))}
      />
      {error && (
        <span role="alert" style={{ fontSize: '0.78rem', color: '#a8402f' }}>
          {error}
        </span>
      )}
    </div>
  );
}

interface NumberFieldProps extends BaseProps {
  value: string;
  onChange: (value: string) => void;
}

/** Labeled numeric input. Deliberately keeps the raw string in state (like
 * the calculator's own number fields) so an in-progress edit (e.g. a lone
 * "-") never gets silently coerced - validation runs on submit. */
export function NumberField({
  theme,
  label,
  value,
  onChange,
  error,
  placeholder,
  required,
}: NumberFieldProps) {
  const id = useId();
  return (
    <div style={wrapStyle}>
      <label htmlFor={id} style={labelStyle(theme)}>{label}</label>
      <input
        id={id}
        type="number"
        inputMode="decimal"
        value={value}
        placeholder={placeholder}
        required={required}
        onChange={(e) => onChange(e.target.value)}
        style={inputStyle(theme, Boolean(error))}
      />
      {error && (
        <span role="alert" style={{ fontSize: '0.78rem', color: '#a8402f' }}>
          {error}
        </span>
      )}
    </div>
  );
}
