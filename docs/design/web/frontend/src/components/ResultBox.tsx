import type { CheckOut } from '../types';
import { STATUS_STYLE } from '../theme';

const ICONS: Record<string, JSX.Element> = {
  pass: <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth={3.5} strokeLinecap="round" strokeLinejoin="round"><path d="M4 12l6 6L20 6" /></svg>,
  near_limit: <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round"><path d="M12 3l10 18H2z" /><line x1="12" y1="10" x2="12" y2="14.5" /><circle cx="12" cy="17.3" r="0.9" fill="#fff" stroke="none" /></svg>,
  fail: <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth={3.5} strokeLinecap="round"><path d="M5 5l14 14M19 5L5 19" /></svg>,
  not_evaluated: <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth={3.5} strokeLinecap="round"><path d="M5 12h14" /></svg>,
};

export default function ResultBox({ check }: { check: CheckOut }) {
  const style = STATUS_STYLE[check.status];
  return (
    <div style={{ background: style.fill, color: '#fff', borderRadius: 14, padding: '14px 12px', minHeight: 128, display: 'flex', flexDirection: 'column', gap: 6, border: style.border }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        {ICONS[check.status]}
        <span style={{ fontWeight: 700, fontSize: '0.82rem', lineHeight: 1.2 }}>{check.label}</span>
      </div>
      <div style={{ fontSize: '0.85rem', fontWeight: 700 }}>{style.label}</div>
      {check.actual != null && check.rating != null && (
        <div style={{ fontSize: '0.72rem', opacity: 0.95, lineHeight: 1.35 }}>{Math.round(check.actual)} lb vs {Math.round(check.rating)} lb</div>
      )}
      {check.status === 'not_evaluated' && check.note && (
        <div style={{ fontSize: '0.68rem', opacity: 0.92, lineHeight: 1.3 }}>{check.note}</div>
      )}
    </div>
  );
}
