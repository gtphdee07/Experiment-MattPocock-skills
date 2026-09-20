import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import Calculator from './Calculator';
import { AuthProvider } from '../auth/AuthContext';
import * as api from '../api';
import type { Account, TrailerProfile, TruckProfile } from '../types';

vi.mock('../api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api')>();
  return { ...actual, getMe: vi.fn(), listTrucks: vi.fn(), listTrailers: vi.fn() };
});

const mockedApi = vi.mocked(api);

const ACCOUNT: Account = {
  id: 1,
  email: 'addie@example.com',
  is_active: true,
  is_verified: false,
  is_superuser: false,
  created_at: '2026-01-01T00:00:00Z',
};

const TRUCK_PROFILE: TruckProfile = {
  id: 5,
  gvwr: 12000,
  front_gawr: 5000,
  rear_gawr: 7000,
  gcwr: 24000,
  nickname: 'Big Blue',
};

const TRAILER_PROFILE: TrailerProfile = {
  id: 9,
  gvwr: 9500,
  gawr: 5200,
  axle_count: 3,
  uvw: 3000,
  nickname: 'Silver Streak',
};

function renderCalculator() {
  return render(
    <MemoryRouter initialEntries={['/']}>
      <AuthProvider>
        <Calculator />
      </AuthProvider>
    </MemoryRouter>
  );
}

// Each test sets exactly the mock behavior it needs (issue #44 added
// listTrucks/listTrailers calls that fire whenever `account` is truthy, so a
// test that signs in but doesn't care about the Garage picker still needs
// them to resolve to *something* rather than leak a previous test's mock).
beforeEach(() => {
  vi.resetAllMocks();
});

describe('Calculator (free, unauthenticated entry point)', () => {
  it('shows real Log in / Register links when signed out, not dead placeholders', async () => {
    mockedApi.getMe.mockRejectedValue(new Error('401'));
    renderCalculator();

    const login = await screen.findByRole('link', { name: 'Log in' });
    const register = screen.getByRole('link', { name: 'Register' });
    expect(login).toHaveAttribute('href', '/login');
    expect(register).toHaveAttribute('href', '/register');
    // The bug this fixes: the header nav used to fall back to dead
    // href="#" "Home"/"About" anchors with no path to sign in at all.
    const nav = screen.getByRole('navigation');
    expect(nav.textContent).not.toMatch(/Home|About/);
  });

  it('shows Garage/History links and the signed-in email when already signed in', async () => {
    mockedApi.getMe.mockResolvedValue(ACCOUNT);
    mockedApi.listTrucks.mockResolvedValue([]);
    mockedApi.listTrailers.mockResolvedValue([]);
    renderCalculator();

    expect(await screen.findByRole('link', { name: 'Garage' })).toHaveAttribute('href', '/garage');
    expect(screen.getByRole('link', { name: 'History' })).toHaveAttribute('href', '/weigh-events');
    expect(screen.getByText('addie@example.com')).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Log in' })).not.toBeInTheDocument();
  });
});

describe('Calculator "load from Garage" picker (issue #44)', () => {
  it('never renders the picker for an anonymous (logged-out) visitor', async () => {
    mockedApi.getMe.mockRejectedValue(new Error('401'));
    renderCalculator();

    // Wait for the signed-out state to settle before asserting an absence.
    await screen.findByRole('link', { name: 'Log in' });
    expect(screen.queryByLabelText('Load from Garage — optional')).not.toBeInTheDocument();
    expect(mockedApi.listTrucks).not.toHaveBeenCalled();
    expect(mockedApi.listTrailers).not.toHaveBeenCalled();
  });

  it('does not render the picker for a logged-in user with an empty Garage', async () => {
    mockedApi.getMe.mockResolvedValue(ACCOUNT);
    mockedApi.listTrucks.mockResolvedValue([]);
    mockedApi.listTrailers.mockResolvedValue([]);
    renderCalculator();

    await screen.findByRole('link', { name: 'Garage' });
    await waitFor(() => expect(mockedApi.listTrucks).toHaveBeenCalled());
    expect(screen.queryByLabelText('Load from Garage — optional')).not.toBeInTheDocument();

    // Same absence holds on the Trailer step.
    await userEvent.type(screen.getByLabelText('GVWR (lb)'), '10000');
    await userEvent.type(screen.getByLabelText('Front GAWR (lb)'), '4500');
    await userEvent.type(screen.getByLabelText('Rear GAWR (lb)'), '6500');
    await userEvent.click(screen.getByRole('button', { name: 'Next' }));
    expect(screen.queryByLabelText('Load from Garage — optional')).not.toBeInTheDocument();
  });

  it('presents saved Profiles and populates the Truck/Trailer fields when one is picked', async () => {
    mockedApi.getMe.mockResolvedValue(ACCOUNT);
    mockedApi.listTrucks.mockResolvedValue([TRUCK_PROFILE]);
    mockedApi.listTrailers.mockResolvedValue([TRAILER_PROFILE]);
    renderCalculator();

    await screen.findByRole('link', { name: 'Garage' });

    const truckPicker = await screen.findByLabelText('Load from Garage — optional');
    await userEvent.selectOptions(truckPicker, 'Big Blue');

    expect(screen.getByLabelText('GVWR (lb)')).toHaveValue(12000);
    expect(screen.getByLabelText('Front GAWR (lb)')).toHaveValue(5000);
    expect(screen.getByLabelText('Rear GAWR (lb)')).toHaveValue(7000);
    expect(screen.getByLabelText('GCWR (lb) — optional')).toHaveValue(24000);

    await userEvent.click(screen.getByRole('button', { name: 'Next' }));

    const trailerPicker = await screen.findByLabelText('Load from Garage — optional');
    await userEvent.selectOptions(trailerPicker, 'Silver Streak');

    expect(screen.getByLabelText('GVWR (lb)')).toHaveValue(9500);
    expect(screen.getByLabelText('GAWR per axle (lb)')).toHaveValue(5200);
    expect(screen.getByLabelText('Axle Count')).toHaveValue(3);
    expect(screen.getByLabelText('UVW (lb) — optional')).toHaveValue(3000);
  });

  it('keeps a manually edited value after picking a Profile - re-picking overwrites, typing afterward does not revert', async () => {
    mockedApi.getMe.mockResolvedValue(ACCOUNT);
    mockedApi.listTrucks.mockResolvedValue([TRUCK_PROFILE]);
    mockedApi.listTrailers.mockResolvedValue([]);
    renderCalculator();

    const truckPicker = await screen.findByLabelText('Load from Garage — optional');
    await userEvent.selectOptions(truckPicker, 'Big Blue');
    expect(screen.getByLabelText('GVWR (lb)')).toHaveValue(12000);

    const gvwrField = screen.getByLabelText('GVWR (lb)');
    await userEvent.clear(gvwrField);
    await userEvent.type(gvwrField, '13500');

    // The edit sticks - picking the same/different profile is the only
    // thing allowed to overwrite it, not some effect re-running.
    expect(screen.getByLabelText('GVWR (lb)')).toHaveValue(13500);
    expect(screen.getByLabelText('Front GAWR (lb)')).toHaveValue(5000);
  });
});
