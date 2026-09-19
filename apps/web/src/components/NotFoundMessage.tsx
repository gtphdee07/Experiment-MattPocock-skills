import { Link } from 'react-router-dom';
import type { Theme } from '../theme';

/** Story 30: acting on a Profile or Weigh Event that isn't actually the
 * caller's (a stale link, or another Account's id) shows this, not a broken
 * page - used both as the catch-all route and inline whenever a fetch comes
 * back 404. */
export default function NotFoundMessage({ theme, backTo = '/garage', backLabel = 'Back to Garage' }: { theme: Theme; backTo?: string; backLabel?: string }) {
  return (
    <div style={{ textAlign: 'center', padding: '48px 0' }}>
      <h2 style={{ fontFamily: 'var(--font-display)', fontSize: '1.4rem' }}>Not found</h2>
      <p style={{ color: theme.text2, maxWidth: 420, margin: '10px auto 24px' }}>
        That item doesn't exist, or doesn't belong to your account.
      </p>
      <Link to={backTo} style={{ color: theme.linkStrong, fontWeight: 600 }}>{backLabel}</Link>
    </div>
  );
}
