import { useEffect, useState } from 'react';
import Card from '../components/Card';
import { PrimaryButton, SecondaryButton } from '../components/form/Button';
import WeighEventResult from '../components/WeighEventResult';
import { useAppTheme } from '../theme/ThemeContext';
import * as api from '../api';
import type { WeighEventOut } from '../types';

const PAGE_SIZE = 20;

/** Full Weigh Event history, newest first (Story 27), paginated rather than
 * loaded all at once (Story 28) - `GET /weigh-events` is already newest-first
 * server-side, so no client-side re-sort is needed. */
export default function WeighEventHistory() {
  const { theme } = useAppTheme();
  const [offset, setOffset] = useState(0);
  const [events, setEvents] = useState<WeighEventOut[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setEvents(null);
    api
      .listWeighEvents(PAGE_SIZE, offset)
      .then((page) => {
        if (!cancelled) setEvents(page);
      })
      .catch(() => {
        if (!cancelled) setError('Could not load your Weigh Event history.');
      });
    return () => {
      cancelled = true;
    };
  }, [offset]);

  return (
    <div>
      <h1 style={{ fontFamily: 'var(--font-display)', fontSize: '1.8rem' }}>Weigh Event History</h1>
      {error && <p role="alert" style={{ color: '#a8402f' }}>{error}</p>}

      {events === null && !error && <p style={{ color: theme.text2 }}>Loading…</p>}

      {events !== null && events.length === 0 && offset === 0 && (
        <p style={{ color: theme.text2 }}>No Weigh Events recorded yet.</p>
      )}

      {events !== null &&
        events.map((event) => (
          <Card key={event.id} theme={theme}>
            <WeighEventResult event={event} />
          </Card>
        ))}

      {events !== null && (
        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 16 }}>
          <SecondaryButton
            theme={theme}
            type="button"
            disabled={offset === 0}
            onClick={() => setOffset((o) => Math.max(0, o - PAGE_SIZE))}
            style={{ width: 120 }}
          >
            Newer
          </SecondaryButton>
          <PrimaryButton
            theme={theme}
            type="button"
            disabled={events.length < PAGE_SIZE}
            onClick={() => setOffset((o) => o + PAGE_SIZE)}
            style={{ width: 120, flex: 'none' }}
          >
            Older
          </PrimaryButton>
        </div>
      )}
    </div>
  );
}
