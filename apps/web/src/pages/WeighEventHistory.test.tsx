import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import WeighEventHistory from './WeighEventHistory';
import { AppThemeProvider } from '../theme/ThemeContext';
import * as api from '../api';
import type { WeighEventOut } from '../types';

vi.mock('../api');
const mockedApi = vi.mocked(api);

function makeEvent(id: number): WeighEventOut {
  return {
    id,
    timestamp: `2026-01-0${id}T00:00:00Z`,
    truck_nickname: `Truck ${id}`,
    trailer_nickname: `Trailer ${id}`,
    overall_status: 'pass',
    checks: [{ label: 'Steer', status: 'pass', actual: 1, rating: 2, note: null }],
    time_gap_hours: null,
    time_gap_exceeds_threshold: null,
    disclaimer: 'd',
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
});
