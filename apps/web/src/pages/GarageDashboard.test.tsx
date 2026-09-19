import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import GarageDashboard from './GarageDashboard';
import { AppThemeProvider } from '../theme/ThemeContext';
import * as api from '../api';
import type { TrailerProfile, TruckProfile } from '../types';

vi.mock('../api');

const mockedApi = vi.mocked(api);

function renderPage() {
  return render(
    <AppThemeProvider>
      <GarageDashboard />
    </AppThemeProvider>
  );
}

describe('GarageDashboard', () => {
  it('shows a computed default Nickname, never a raw ID, for an un-nicknamed Truck (Story 11)', async () => {
    const truck: TruckProfile = {
      id: 3,
      gvwr: 10000,
      front_gawr: 4500,
      rear_gawr: 6500,
      gcwr: null,
      nickname: 'Truck 3',
    };
    mockedApi.listTrucks.mockResolvedValue([truck]);
    mockedApi.listTrailers.mockResolvedValue([]);

    renderPage();

    expect(await screen.findByText('Truck 3')).toBeInTheDocument();
    expect(screen.queryByText('3')).not.toBeInTheDocument();
  });

  it('lists every Truck and Trailer Profile in the Garage (Story 9/14)', async () => {
    const trucks: TruckProfile[] = [
      { id: 1, gvwr: 1, front_gawr: 1, rear_gawr: 1, gcwr: null, nickname: 'Addie' },
      { id: 2, gvwr: 1, front_gawr: 1, rear_gawr: 1, gcwr: null, nickname: 'Truck 2' },
    ];
    const trailers: TrailerProfile[] = [
      { id: 5, gvwr: 1, gawr: 1, axle_count: 2, uvw: null, nickname: 'Goose' },
    ];
    mockedApi.listTrucks.mockResolvedValue(trucks);
    mockedApi.listTrailers.mockResolvedValue(trailers);

    renderPage();

    expect(await screen.findByText('Addie')).toBeInTheDocument();
    expect(screen.getByText('Truck 2')).toBeInTheDocument();
    expect(screen.getByText('Goose')).toBeInTheDocument();
  });

  it('deletes a Truck Profile only after the confirm step (Story 13)', async () => {
    const user = userEvent.setup();
    const truck: TruckProfile = { id: 9, gvwr: 1, front_gawr: 1, rear_gawr: 1, gcwr: null, nickname: 'Addie' };
    mockedApi.listTrucks.mockResolvedValue([truck]);
    mockedApi.listTrailers.mockResolvedValue([]);
    mockedApi.deleteTruck.mockResolvedValue(undefined);

    renderPage();
    await screen.findByText('Addie');

    await user.click(screen.getByRole('button', { name: 'Delete' }));
    expect(mockedApi.deleteTruck).not.toHaveBeenCalled();

    await user.click(screen.getByRole('button', { name: 'Yes, delete' }));
    await waitFor(() => expect(mockedApi.deleteTruck).toHaveBeenCalledWith(9));
  });
});
