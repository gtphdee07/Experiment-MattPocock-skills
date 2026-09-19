import type { ReactNode } from 'react';
import type { Theme } from '../theme';

/** The calculator's rounded surface card, extracted as a shared shell for
 * every new page (issue #30 Implementation Decisions: reuse `theme.ts`'s
 * tokens, not a new design system). */
export default function Card({ theme, children }: { theme: Theme; children: ReactNode }) {
  return (
    <div
      style={{
        marginTop: 20,
        background: theme.surface,
        border: `1px solid ${theme.border}`,
        borderRadius: 24,
        padding: '36px 40px',
        boxShadow: '0 12px 40px rgba(0,0,0,0.06)',
      }}
    >
      {children}
    </div>
  );
}
