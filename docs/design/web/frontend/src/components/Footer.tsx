import type { Theme } from '../theme';

export default function Footer({ theme }: { theme: Theme }) {
  return (
    <footer style={{ maxWidth: 1100, margin: '0 auto', padding: '28px 32px 44px', borderTop: `1px solid ${theme.border}`, display: 'flex', flexWrap: 'wrap', gap: 16, alignItems: 'center', justifyContent: 'space-between' }}>
      <p style={{ margin: 0, fontSize: '0.75rem', color: theme.text2, maxWidth: 600, lineHeight: 1.5 }}>
        This tool is for reference only and is not a substitute for certified scale readings or manufacturer documentation. Wandering Trails, Wagging Tails.
      </p>
      <div style={{ display: 'flex', gap: 20 }}>
        <a href="#" style={{ color: theme.text2, fontSize: '0.8rem', textDecoration: 'none' }}>Home</a>
        <a href="#" style={{ color: theme.text2, fontSize: '0.8rem', textDecoration: 'none' }}>About</a>
      </div>
    </footer>
  );
}
