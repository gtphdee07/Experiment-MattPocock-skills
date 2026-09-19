import type { ButtonHTMLAttributes } from 'react';
import type { Theme } from '../../theme';
import { ORANGE, GREEN } from '../../theme';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  theme: Theme;
  full?: boolean;
}

/** The calculator's solid-orange "Next"/submit button, extracted verbatim as
 * a shared primitive (issue #30 Implementation Decisions). */
export function PrimaryButton({ theme, full, style, disabled, ...rest }: ButtonProps) {
  return (
    <button
      disabled={disabled}
      style={{
        height: 50,
        width: full ? '100%' : undefined,
        flex: full ? undefined : 1,
        borderRadius: 999,
        border: 'none',
        background: ORANGE,
        color: '#fff',
        fontFamily: 'var(--font-display)',
        fontWeight: 700,
        fontSize: '1rem',
        cursor: disabled ? 'default' : 'pointer',
        opacity: disabled ? 0.5 : 1,
        ...style,
      }}
      {...rest}
    />
  );
}

/** The calculator's outlined "Back" button, extracted verbatim. */
export function SecondaryButton({ theme, style, ...rest }: ButtonProps) {
  return (
    <button
      style={{
        height: 50,
        borderRadius: 999,
        border: `2px solid ${GREEN}`,
        background: 'transparent',
        color: theme.linkStrong,
        fontFamily: 'var(--font-display)',
        fontWeight: 700,
        fontSize: '0.95rem',
        cursor: 'pointer',
        ...style,
      }}
      {...rest}
    />
  );
}
