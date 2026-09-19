import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import Card from '../components/Card';
import { TextField } from '../components/form/Field';
import { PrimaryButton } from '../components/form/Button';
import { useAppTheme } from '../theme/ThemeContext';
import { useAuth } from '../auth/AuthContext';
import { ApiError, login as loginRequest, register as registerAccount } from '../api';

/** Reads fastapi-users' register error shapes (issue #30 spec: verified
 * against apps/backend/tests/test_http_auth_flow.py) into the inline message
 * Story 3 wants - duplicate email ("REGISTER_USER_ALREADY_EXISTS") and a
 * too-short/weak password (`{code: "REGISTER_INVALID_PASSWORD", reason}`). */
function registerErrorMessage(detail: unknown): string {
  if (detail === 'REGISTER_USER_ALREADY_EXISTS') {
    return 'That email is already registered. Try logging in instead.';
  }
  if (detail && typeof detail === 'object' && 'code' in detail) {
    const code = (detail as { code?: string }).code;
    if (code === 'REGISTER_INVALID_PASSWORD') {
      const reason = (detail as { reason?: string }).reason;
      return reason ?? 'That password is too short or too weak.';
    }
  }
  return 'Could not register. Please check your details and try again.';
}

export default function Register() {
  const { theme } = useAppTheme();
  const { refresh } = useAuth();
  const navigate = useNavigate();

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
      await registerAccount(email, password);
      // #18's `POST /auth/register` only creates the Account - it doesn't
      // set a session cookie (fastapi-users' standard behavior). Log in
      // immediately afterward with the same credentials so registering
      // actually lands the visitor signed in, matching Story 2's intent.
      await loginRequest(email, password);
      await refresh();
      navigate('/garage');
    } catch (err) {
      // Deliberately keeps `email`/`password` state untouched on error
      // (Story 3: "without losing what was already typed").
      if (err instanceof ApiError) {
        setError(registerErrorMessage(err.detail));
      } else {
        setError('Could not reach the server. Please try again.');
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div style={{ maxWidth: 440, margin: '0 auto' }}>
      <h1 style={{ fontFamily: 'var(--font-display)', fontSize: '1.7rem', textAlign: 'center' }}>
        Create an account
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
            autoComplete="new-password"
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
            {submitting ? 'Creating account…' : 'Register'}
          </PrimaryButton>
        </form>
      </Card>
      <p style={{ textAlign: 'center', marginTop: 16, fontSize: '0.9rem', color: theme.text2 }}>
        Already have an account? <Link to="/login" style={{ color: theme.linkStrong }}>Log in</Link>
      </p>
    </div>
  );
}
