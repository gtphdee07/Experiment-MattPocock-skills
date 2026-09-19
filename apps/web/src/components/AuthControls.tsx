import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';

const linkStyle = { color: 'inherit', fontSize: '0.92rem', fontWeight: 600, textDecoration: 'none' } as const;

/** The signed-in-state slot every page's `Header` shows: Log in/Register
 * links when signed out, email + Log out when signed in (Stories 2/4/6/7).
 * Extracted so the calculator - the one page a fully anonymous visitor
 * actually lands on - can show the same real controls `AuthedLayout`
 * already did, instead of nothing at all (the bug this fixes: there was no
 * discoverable path from `/` to `/login` or `/register` anywhere). */
export default function AuthControls() {
  const { account, logout } = useAuth();
  const navigate = useNavigate();

  async function handleLogout() {
    await logout();
    navigate('/login');
  }

  if (account) {
    return (
      <span style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
        <span style={{ fontSize: '0.85rem' }}>{account.email}</span>
        <button
          onClick={() => void handleLogout()}
          style={{
            height: 34,
            padding: '0 14px',
            borderRadius: 999,
            border: '1.5px solid currentColor',
            background: 'transparent',
            color: 'inherit',
            fontWeight: 600,
            fontSize: '0.82rem',
            cursor: 'pointer',
          }}
        >
          Log out
        </button>
      </span>
    );
  }

  return (
    <span style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
      <Link to="/login" style={linkStyle}>
        Log in
      </Link>
      <Link to="/register" style={linkStyle}>
        Register
      </Link>
    </span>
  );
}
