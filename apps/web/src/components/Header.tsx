import type { ReactNode } from 'react';
import type { Theme, Mode } from '../theme';

interface Props {
  theme: Theme;
  mode: Mode;
  onToggleTheme: () => void;
  /** Optional real nav links for the authenticated shell. When omitted, the
   * original placeholder Home/About anchors render unchanged - the free
   * calculator (issue #30 Story 1/32) never passes this. */
  navLinks?: ReactNode;
  /** Optional signed-in-state slot (email + logout) for the authenticated
   * shell. Omitted entirely for the calculator. */
  authControls?: ReactNode;
}

export default function Header({ theme, mode, onToggleTheme, navLinks, authControls }: Props) {
  return (
    <header style={{ maxWidth: 1100, margin: '0 auto', padding: '22px 32px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 24 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <img src="/assets/wtwt-logo.png" alt="Wandering Trails, Wagging Tails" style={{ height: 40, width: 40, objectFit: 'cover', borderRadius: 10 }} />
        <div style={{ fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: '1.15rem', color: theme.text }}>Towing Limit Checker</div>
      </div>
      <nav style={{ display: 'flex', alignItems: 'center', gap: 28 }}>
        {navLinks ?? (
          <>
            <a href="#" style={{ color: theme.text, fontSize: '0.92rem', fontWeight: 600, textDecoration: 'none' }}>Home</a>
            <a href="#" style={{ color: theme.text, fontSize: '0.92rem', fontWeight: 600, textDecoration: 'none' }}>About</a>
          </>
        )}
        {authControls}
        <button
          onClick={onToggleTheme}
          aria-label="Toggle dark mode"
          style={{ width: 38, height: 38, borderRadius: 999, border: `1.5px solid ${theme.border}`, background: theme.surface, display: 'flex', alignItems: 'center', justifyContent: 'center', cursor: 'pointer' }}
        >
          {mode === 'dark' ? (
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#f6efe4" strokeWidth={2}><path d="M21 12.8A9 9 0 1 1 11.2 3 7 7 0 0 0 21 12.8z" /></svg>
          ) : (
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#2a2a28" strokeWidth={2} strokeLinecap="round"><circle cx="12" cy="12" r="4.5" /><path d="M12 2v3M12 19v3M4.2 4.2l2.1 2.1M17.7 17.7l2.1 2.1M2 12h3M19 12h3M4.2 19.8l2.1-2.1M17.7 6.3l2.1-2.1" /></svg>
          )}
        </button>
      </nav>
    </header>
  );
}
