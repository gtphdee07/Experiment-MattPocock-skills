import { Link, Outlet, useNavigate } from 'react-router-dom';
import Header from './Header';
import Footer from './Footer';
import { useAppTheme } from '../theme/ThemeContext';
import { useAuth } from '../auth/AuthContext';

const linkStyle = { color: 'inherit', fontSize: '0.92rem', fontWeight: 600, textDecoration: 'none' } as const;

/** The shell for every page beyond the free calculator: real nav links
 * (Calculator / Garage / History), signed-in state (Story 6), and Logout
 * (Story 7) - built on the same `Header`/`Footer` the calculator uses, via
 * `Header`'s optional `navLinks`/`authControls` slots. */
export default function AuthedLayout() {
  const { theme, mode, toggle } = useAppTheme();
  const { account, logout } = useAuth();
  const navigate = useNavigate();

  async function handleLogout() {
    await logout();
    navigate('/login');
  }

  return (
    <div style={{ minHeight: '100vh', background: theme.page, color: theme.text, fontFamily: 'var(--font-body)' }}>
      <Header
        theme={theme}
        mode={mode}
        onToggleTheme={toggle}
        navLinks={
          <>
            <Link to="/" style={{ ...linkStyle, color: theme.text }}>Calculator</Link>
            {account && (
              <>
                <Link to="/garage" style={{ ...linkStyle, color: theme.text }}>Garage</Link>
                <Link to="/weigh-events/new" style={{ ...linkStyle, color: theme.text }}>New Weigh Event</Link>
                <Link to="/weigh-events" style={{ ...linkStyle, color: theme.text }}>History</Link>
              </>
            )}
          </>
        }
        authControls={
          account ? (
            <span style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
              <span style={{ fontSize: '0.85rem', color: theme.text2 }}>{account.email}</span>
              <button
                onClick={() => void handleLogout()}
                style={{
                  height: 34,
                  padding: '0 14px',
                  borderRadius: 999,
                  border: `1.5px solid ${theme.border}`,
                  background: 'transparent',
                  color: theme.text,
                  fontWeight: 600,
                  fontSize: '0.82rem',
                  cursor: 'pointer',
                }}
              >
                Log out
              </button>
            </span>
          ) : (
            <span style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
              <Link to="/login" style={{ ...linkStyle, color: theme.text }}>Log in</Link>
              <Link to="/register" style={{ ...linkStyle, color: theme.text }}>Register</Link>
            </span>
          )
        }
      />
      <main style={{ maxWidth: 760, margin: '0 auto', padding: '8px 24px 64px' }}>
        <Outlet />
      </main>
      <Footer theme={theme} />
    </div>
  );
}
