import ResultBox from './ResultBox';
import { BANNER, BANNER_MESSAGE } from '../theme';
import type { Theme } from '../theme';
import { useAppTheme } from '../theme/ThemeContext';
import type { WeighEventOut } from '../types';

/** Wraps the calculator's own results grid (`ResultBox`, unmodified) with
 * the new framing a persisted Weigh Event needs - id/timestamp/Nicknames
 * (issue #30 Story 25/29/32: "reusing the calculator's own results
 * rendering... only new framing wraps the same grid"). */
// Issue #45 / ADR 0017: a small, always-visible marker for a One-Off Truck/
// Trailer - shown whenever that side's `truck_id`/`trailer_id` is `null`,
// regardless of whether it has a Nickname (Story 4: never mistaken for a
// real, reusable Garage Profile).
function OneOffBadge({ theme }: { theme: Theme }) {
  return (
    <span
      style={{
        display: 'inline-block',
        marginLeft: 6,
        padding: '1px 8px',
        borderRadius: 999,
        fontSize: '0.7rem',
        fontWeight: 700,
        color: theme.text2,
        border: `1px solid ${theme.border}`,
        verticalAlign: 'middle',
      }}
    >
      (one-off)
    </span>
  );
}

export default function WeighEventResult({ event }: { event: WeighEventOut }) {
  const { theme, mode } = useAppTheme();
  const banner = BANNER[mode][event.overall_status];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8 }}>
        <div style={{ fontWeight: 700 }}>
          <span>{event.truck_nickname}</span>
          {event.truck_id === null && <OneOffBadge theme={theme} />} +{' '}
          <span>{event.trailer_nickname}</span>
          {event.trailer_id === null && <OneOffBadge theme={theme} />}
        </div>
        <div style={{ color: theme.text2, fontSize: '0.85rem' }}>
          {new Date(event.timestamp).toLocaleString()}
        </div>
      </div>
      <div style={{ marginTop: 12, padding: '16px 18px', borderRadius: 14, background: banner.bg, color: banner.text, fontSize: '0.95rem', lineHeight: 1.5, fontWeight: 500 }}>
        {BANNER_MESSAGE[event.overall_status]}
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12, marginTop: 16 }}>
        {event.checks.map((c, i) => (
          <ResultBox key={i} check={c} />
        ))}
      </div>
      {event.time_gap_hours != null && event.time_gap_exceeds_threshold && (
        <div style={{ marginTop: 14, padding: '12px 14px', borderRadius: 12, background: theme.infoBg, color: theme.infoText, fontSize: '0.82rem', lineHeight: 1.5 }}>
          Time-Gap Warning (advisory): the two physical weighings were about {Math.abs(event.time_gap_hours)} hours apart.
        </div>
      )}
      <p style={{ margin: '14px 0 0', fontSize: '0.7rem', color: theme.text2, lineHeight: 1.5 }}>{event.disclaimer}</p>
    </div>
  );
}
