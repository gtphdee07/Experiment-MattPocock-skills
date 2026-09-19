import { Link, Outlet } from 'react-router-dom';
import Header from './Header';
import Footer from './Footer';
import AuthControls from './AuthControls';
import { useAppTheme } from '../theme/ThemeContext';
import { useAuth } from '../auth/AuthContext';

const linkStyle = { color: 'inherit', fontSize: '0.92rem', fontWeight: 600, textDecoration: 'none' } as const;

/** The shell for every page beyond the free calculator: real nav links
 * (Calculator / Garage / History) plus `AuthControls` (Stories 2/4/6/7) -
 * built on the same `Header`/`Footer` the calculator uses, via `Header`'s
 * `navLinks`/`authControls` slots. */
export default function AuthedLayout() {
  const { theme, mode, toggle } = useAppTheme();
  const { account } = useAuth();

  return (
    <div style={{ minHeight: '100vh', background: theme.page, color: theme.text, fontFamily: 'var(--font-body)' }}>
      <Header
        theme={theme}
        mode={mode}
        onToggleTheme={toggle}
        navLinks={
          <>
            <Link to="/" style={linkStyle}>Calculator</Link>
            {account && (
              <>
                <Link to="/garage" style={linkStyle}>Garage</Link>
                <Link to="/weigh-events/new" style={linkStyle}>New Weigh Event</Link>
                <Link to="/weigh-events" style={linkStyle}>History</Link>
              </>
            )}
          </>
        }
        authControls={<AuthControls />}
      />
      <main style={{ maxWidth: 760, margin: '0 auto', padding: '8px 24px 64px' }}>
        <Outlet />
      </main>
      <Footer theme={theme} />
    </div>
  );
}
