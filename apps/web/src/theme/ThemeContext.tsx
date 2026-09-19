import { createContext, useContext, useState } from 'react';
import type { ReactNode } from 'react';
import { LIGHT, DARK } from '../theme';
import type { Theme, Mode } from '../theme';

interface ThemeState {
  theme: Theme;
  mode: Mode;
  toggle: () => void;
}

const ThemeCtx = createContext<ThemeState | null>(null);

/** The authenticated shell's own light/dark toggle, kept separate from
 * `App.tsx`'s (the free calculator's, left untouched per issue #30 Story 32)
 * - a deliberate small duplication rather than threading the calculator's
 * local state through a new provider boundary it was never built for. */
export function AppThemeProvider({ children }: { children: ReactNode }) {
  const [mode, setMode] = useState<Mode>('light');
  const theme = mode === 'dark' ? DARK : LIGHT;
  const toggle = () => setMode((m) => (m === 'light' ? 'dark' : 'light'));
  return <ThemeCtx.Provider value={{ theme, mode, toggle }}>{children}</ThemeCtx.Provider>;
}

export function useAppTheme(): ThemeState {
  const ctx = useContext(ThemeCtx);
  if (!ctx) throw new Error('useAppTheme must be used within an AppThemeProvider');
  return ctx;
}
