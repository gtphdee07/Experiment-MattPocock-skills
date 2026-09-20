import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import WeighEventHistory from './WeighEventHistory';
import { AppThemeProvider } from '../theme/ThemeContext';
import * as api from '../api';
import type { WeighEventOut } from '../types';

vi.mock('../api');
const mockedApi = vi.mocked(api);

function makeEvent(id: number, overrides: Partial<WeighEventOut> = {}): WeighEventOut {
  return {
    id,
    timestamp: `2026-01-0${id}T00:00:00Z`,
    truck_nickname: `Truck ${id}`,
    trailer_nickname: `Trailer ${id}`,
    truck_id: id,
    trailer_id: id,
    overall_status: 'pass',
    checks: [{ label: 'Steer', status: 'pass', actual: 1, rating: 2, note: null }],
    time_gap_hours: null,
    time_gap_exceeds_threshold: null,
    disclaimer: 'd',
    ...overrides,
  };
}

function renderPage() {
  return render(
    <AppThemeProvider>
      <WeighEventHistory />
    </AppThemeProvider>
  );
}

describe('WeighEventHistory', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('loads a page of 20 at offset 0 and requests the next page on "Older" (Story 27/28)', async () => {
    const user = userEvent.setup();
    const fullPage = Array.from({ length: 20 }, (_, i) => makeEvent(i + 1));
    mockedApi.listWeighEvents.mockResolvedValueOnce(fullPage);

    renderPage();

    expect(await screen.findByText('Truck 1')).toBeInTheDocument();
    expect(mockedApi.listWeighEvents).toHaveBeenCalledWith(20, 0);

    const secondPage = [makeEvent(21)];
    mockedApi.listWeighEvents.mockResolvedValueOnce(secondPage);
    await user.click(screen.getByRole('button', { name: 'Older' }));

    await waitFor(() => expect(mockedApi.listWeighEvents).toHaveBeenCalledWith(20, 20));
    expect(await screen.findByText('Truck 21')).toBeInTheDocument();
  });

  it('disables "Older" once a short page proves there is no more history', async () => {
    mockedApi.listWeighEvents.mockResolvedValueOnce([makeEvent(1)]);
    renderPage();

    await screen.findByText('Truck 1');
    expect(screen.getByRole('button', { name: 'Older' })).toBeDisabled();
  });

  it('shows each entry\'s Truck/Trailer Nickname (Story 29)', async () => {
    mockedApi.listWeighEvents.mockResolvedValueOnce([makeEvent(7)]);
    renderPage();

    expect(await screen.findByText('Truck 7')).toBeInTheDocument();
    expect(screen.getByText('Trailer 7')).toBeInTheDocument();
  });

  // --- Issue #45 / ADR 0017: One-Off Truck/Trailer badge/fallback ---------

  it('shows a "(one-off)" badge for a One-Off entry even when it has a Nickname (Story 4)', async () => {
    mockedApi.listWeighEvents.mockResolvedValueOnce([
      makeEvent(1, { truck_id: null, truck_nickname: 'Borrowed Bertha' }),
    ]);
    renderPage();

    await screen.findByText('Borrowed Bertha');
    expect(screen.getAllByText('(one-off)')).toHaveLength(1);
  });

  it('shows the distinct "One-Off Truck"/"One-Off Trailer" fallback label, not an ID-derived one (Story 5)', async () => {
    mockedApi.listWeighEvents.mockResolvedValueOnce([
      makeEvent(1, {
        truck_id: null,
        trailer_id: null,
        truck_nickname: 'One-Off Truck',
        trailer_nickname: 'One-Off Trailer',
      }),
    ]);
    renderPage();

    expect(await screen.findByText('One-Off Truck')).toBeInTheDocument();
    expect(screen.getByText('One-Off Trailer')).toBeInTheDocument();
    expect(screen.getAllByText('(one-off)')).toHaveLength(2);
  });

  it('shows no "(one-off)" badge for an entry with two real, saved Profiles', async () => {
    mockedApi.listWeighEvents.mockResolvedValueOnce([makeEvent(3)]);
    renderPage();

    await screen.findByText('Truck 3');
    expect(screen.queryByText('(one-off)')).not.toBeInTheDocument();
  });
});
