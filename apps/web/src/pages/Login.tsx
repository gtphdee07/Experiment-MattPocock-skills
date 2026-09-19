import { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import Card from '../components/Card';
import { TextField } from '../components/form/Field';
import { PrimaryButton } from '../components/form/Button';
import { useAppTheme } from '../theme/ThemeContext';
import { useAuth } from '../auth/AuthContext';
import { login as loginRequest } from '../api';

const GENERIC_INVALID_CREDENTIALS =
  'That email and password combination is not valid. Please try again.';

export default function Login() {
  const { theme } = useAppTheme();
  const { refresh } = useAuth();
  const navigate = useNavigate();
  const location = useLocation() as { state?: { from?: { pathname?: string } } };

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const valid = email.trim() !== '' && password.length > 0;

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!valid) return;
    setSubmitting(true);
    setError(null);
    try {
      await loginRequest(email, password);
      await refresh();
      const dest = location.state?.from?.pathname ?? '/garage';
      navigate(dest, { replace: true });
    } catch {
      // Story 5: never reveal whether the email or the password was wrong -
      // one generic message for every failure mode, including a network/
      // server error, which is indistinguishable to the visitor anyway.
      setError(GENERIC_INVALID_CREDENTIALS);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div style={{ maxWidth: 440, margin: '0 auto' }}>
      <h1 style={{ fontFamily: 'var(--font-display)', fontSize: '1.7rem', textAlign: 'center' }}>
        Log in
      </h1>
      <Card theme={theme}>
        <form onSubmit={(e) => void onSubmit(e)} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <TextField
            theme={theme}
            label="Email"
            type="email"
            autoComplete="email"
            value={email}
            onChange={setEmail}
            required
          />
          <TextField
            theme={theme}
            label="Password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={setPassword}
            required
          />
          {error && (
            <p role="alert" style={{ margin: 0, fontSize: '0.85rem', color: '#a8402f' }}>
              {error}
            </p>
          )}
          <PrimaryButton theme={theme} full type="submit" disabled={!valid || submitting}>
            {submitting ? 'Signing in…' : 'Log in'}
          </PrimaryButton>
        </form>
      </Card>
      <p style={{ textAlign: 'center', marginTop: 16, fontSize: '0.9rem', color: theme.text2 }}>
        Need an account? <Link to="/register" style={{ color: theme.linkStrong }}>Register</Link>
      </p>
    </div>
  );
}
