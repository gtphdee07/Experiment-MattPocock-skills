import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import WeighEventNew from './WeighEventNew';
import { AppThemeProvider } from '../theme/ThemeContext';
import { ApiError } from '../api';
import * as api from '../api';
import type { TrailerProfile, TruckProfile, WeighEventOut } from '../types';

// A partial mock (not a full `vi.mock('../api')` automock) - automocking
// would also replace the `ApiError` class export, breaking the component's
// own `err instanceof ApiError` narrowing for the 409 confirm-link branch.
vi.mock('../api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api')>();
  return {
    ...actual,
    listTrucks: vi.fn(),
    listTrailers: vi.fn(),
    getReusableSoloTicket: vi.fn(),
    createWeighEvent: vi.fn(),
    createTruck: vi.fn(),
    createTrailer: vi.fn(),
  };
});
const mockedApi = vi.mocked(api);

const truck: TruckProfile = { id: 1, gvwr: 10000, front_gawr: 4500, rear_gawr: 6500, gcwr: 20000, nickname: 'Addie' };
const trailer: TrailerProfile = { id: 2, gvwr: 9500, gawr: 5200, axle_count: 2, uvw: null, nickname: 'Goose' };

const okEvent: WeighEventOut = {
  id: 1,
  timestamp: '2026-01-01T00:00:00Z',
  truck_nickname: 'Addie',
  trailer_nickname: 'Goose',
  truck_id: 1,
  trailer_id: 2,
  overall_status: 'pass',
  checks: [{ label: 'Steer', status: 'pass', actual: 4000, rating: 4500, note: null }],
  time_gap_hours: null,
  time_gap_exceeds_threshold: null,
  disclaimer: 'disclaimer text',
};

function renderPage() {
  return render(
    <MemoryRouter>
      <AppThemeProvider>
        <WeighEventNew />
      </AppThemeProvider>
    </MemoryRouter>
  );
}

async function pickProfilesAndFillCombined(user: ReturnType<typeof userEvent.setup>) {
  await screen.findByText('Pick a Truck and Trailer');
  await user.selectOptions(screen.getByLabelText('Truck Profile'), '1');
  await user.selectOptions(screen.getByLabelText('Trailer Profile'), '2');
  await user.click(screen.getByRole('button', { name: 'Next' }));

  await screen.findByText('Combined Ticket');
  await user.type(screen.getByLabelText('Steer Axle (lb)'), '4300');
  await user.type(screen.getByLabelText('Drive Axle (lb)'), '6100');
  await user.type(screen.getByLabelText('Trailer Axle group (lb)'), '9200');
  await user.type(screen.getByLabelText('Gross Weight (lb)'), '19600');
  await user.click(screen.getByRole('button', { name: 'Next' }));
  await screen.findByText('Solo Ticket');
}

describe('WeighEventNew', () => {
  // Issue #45 / ADR 0017: the old Story 17 "blocked entirely, go to /garage
  // first" behavior is exactly the problem this issue solves - an empty
  // Garage no longer blocks the picker, since a One-Off Truck/Trailer needs
  // no saved Profile at all.
  it('does not block the picker when the Garage is empty - a One-Off can be entered instead', async () => {
    mockedApi.listTrucks.mockResolvedValue([]);
    mockedApi.listTrailers.mockResolvedValue([]);
    renderPage();

    await screen.findByText('Pick a Truck and Trailer');
    expect(screen.queryByText('Add a Truck and Trailer Profile first')).not.toBeInTheDocument();
    expect(
      screen.getByRole('option', { name: 'Enter a one-off Truck' })
    ).toBeInTheDocument();
    expect(
      screen.getByRole('option', { name: 'Add new Truck to my Garage' })
    ).toBeInTheDocument();
  });

  it('offers One-Off and Add-new sentinel options above the saved Profile list', async () => {
    mockedApi.listTrucks.mockResolvedValue([truck]);
    mockedApi.listTrailers.mockResolvedValue([trailer]);
    renderPage();

    await screen.findByText('Pick a Truck and Trailer');
    expect(screen.getByRole('option', { name: 'Enter a one-off Trailer' })).toBeInTheDocument();
    expect(
      screen.getByRole('option', { name: 'Add new Trailer to my Garage' })
    ).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Addie' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Goose' })).toBeInTheDocument();
  });

  it('records a One-Off Truck with a saved Trailer, and skips the reusable-Solo-Ticket check (Story 1/2/8)', async () => {
    const user = userEvent.setup();
    mockedApi.listTrucks.mockResolvedValue([]);
    mockedApi.listTrailers.mockResolvedValue([trailer]);
    mockedApi.createWeighEvent.mockResolvedValue(okEvent);

    renderPage();
    await screen.findByText('Pick a Truck and Trailer');
    await user.selectOptions(screen.getByLabelText('Truck Profile'), 'Enter a one-off Truck');
    await user.type(screen.getByLabelText('GVWR (lb)'), '9000');
    await user.type(screen.getByLabelText('Front GAWR (lb)'), '4000');
    await user.type(screen.getByLabelText('Rear GAWR (lb)'), '5200');
    await user.click(screen.getByRole('button', { name: 'Use this Truck' }));

    await user.selectOptions(screen.getByLabelText('Trailer Profile'), '2');
    await user.click(screen.getByRole('button', { name: 'Next' }));

    await screen.findByText('Combined Ticket');
    await user.type(screen.getByLabelText('Steer Axle (lb)'), '4300');
    await user.type(screen.getByLabelText('Drive Axle (lb)'), '6100');
    await user.type(screen.getByLabelText('Trailer Axle group (lb)'), '9200');
    await user.type(screen.getByLabelText('Gross Weight (lb)'), '19600');
    await user.click(screen.getByRole('button', { name: 'Next' }));

    await screen.findByText('Solo Ticket');
    // Story 8: a One-Off Truck has no history - the reusable-Solo-Ticket
    // lookup is never called, and the page treats it as resolved to null.
    expect(mockedApi.getReusableSoloTicket).not.toHaveBeenCalled();
    expect(screen.getByText(/No reusable Solo weight/)).toBeInTheDocument();

    await user.click(screen.getByLabelText('Skip the Solo Ticket'));
    await user.click(screen.getByRole('button', { name: 'See results' }));

    await waitFor(() =>
      expect(mockedApi.createWeighEvent).toHaveBeenCalledWith(
        expect.objectContaining({
          truck: { gvwr: 9000, front_gawr: 4000, rear_gawr: 5200, gcwr: null, nickname: null },
          trailer_id: 2,
        })
      )
    );
    const call = mockedApi.createWeighEvent.mock.calls[0][0];
    expect(call.truck_id).toBeUndefined();
  });

  it('adds a brand-new Truck Profile inline and auto-selects it back in the picker (Story 6/7)', async () => {
    const user = userEvent.setup();
    mockedApi.listTrucks.mockResolvedValue([]);
    mockedApi.listTrailers.mockResolvedValue([trailer]);
    const createdTruck = { id: 9, gvwr: 11000, front_gawr: 5000, rear_gawr: 6000, gcwr: null, nickname: 'New Truck' };
    mockedApi.createTruck.mockResolvedValue(createdTruck);
    mockedApi.getReusableSoloTicket.mockResolvedValue(null);
    mockedApi.createWeighEvent.mockResolvedValue(okEvent);

    renderPage();
    await screen.findByText('Pick a Truck and Trailer');
    await user.selectOptions(screen.getByLabelText('Truck Profile'), 'Add new Truck to my Garage');
    await user.type(screen.getByLabelText('GVWR (lb)'), '11000');
    await user.type(screen.getByLabelText('Front GAWR (lb)'), '5000');
    await user.type(screen.getByLabelText('Rear GAWR (lb)'), '6000');
    await user.type(screen.getByLabelText('Nickname — optional'), 'New Truck');
    await user.click(screen.getByRole('button', { name: 'Add Truck' }));

    await waitFor(() => expect(mockedApi.createTruck).toHaveBeenCalled());
    // Auto-selected back in the picker - the select now shows the new
    // Profile, not the inline form.
    expect(await screen.findByRole('option', { name: 'New Truck', selected: true })).toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText('Trailer Profile'), '2');
    await user.click(screen.getByRole('button', { name: 'Next' }));

    await waitFor(() => expect(mockedApi.getReusableSoloTicket).toHaveBeenCalledWith(9));
  });

  it('offers reuse-unchanged, reuse-adjusted, and fresh-solo branches when a reusable weight exists (Story 19-22)', async () => {
    const user = userEvent.setup();
    mockedApi.listTrucks.mockResolvedValue([truck]);
    mockedApi.listTrailers.mockResolvedValue([trailer]);
    mockedApi.getReusableSoloTicket.mockResolvedValue({ gross: 10500, from_timestamp: '2025-12-01T00:00:00Z' });
    mockedApi.createWeighEvent.mockResolvedValue(okEvent);

    renderPage();
    await pickProfilesAndFillCombined(user);

    expect(await screen.findByText(/A past Solo weight is available/)).toBeInTheDocument();
    expect(screen.getByLabelText('Reuse the past Solo weight')).toBeInTheDocument();
    expect(screen.getByLabelText('Enter a new Solo Ticket')).toBeInTheDocument();
    expect(screen.getByLabelText('Skip the Solo Ticket')).toBeInTheDocument();

    // Story 20: reuse unchanged.
    await user.click(screen.getByLabelText('Reuse the past Solo weight'));
    await user.click(screen.getByRole('button', { name: 'See results' }));

    await waitFor(() =>
      expect(mockedApi.createWeighEvent).toHaveBeenCalledWith(
        expect.objectContaining({
          solo: { kind: 'reused', from_timestamp: '2025-12-01T00:00:00Z', gross: 10500, adjusted: false },
        })
      )
    );
  });

  it('sends adjusted: true with the edited weight when the reused solo is adjusted (Story 21)', async () => {
    const user = userEvent.setup();
    mockedApi.listTrucks.mockResolvedValue([truck]);
    mockedApi.listTrailers.mockResolvedValue([trailer]);
    mockedApi.getReusableSoloTicket.mockResolvedValue({ gross: 10500, from_timestamp: '2025-12-01T00:00:00Z' });
    mockedApi.createWeighEvent.mockResolvedValue(okEvent);

    renderPage();
    await pickProfilesAndFillCombined(user);

    await user.click(screen.getByLabelText('Reuse the past Solo weight'));
    await user.click(screen.getByLabelText('Something has changed since then (adjust the weight)'));
    const adjustedField = await screen.findByLabelText('Adjusted Solo Gross Weight (lb)');
    await user.clear(adjustedField);
    await user.type(adjustedField, '10800');
    await user.click(screen.getByRole('button', { name: 'See results' }));

    await waitFor(() =>
      expect(mockedApi.createWeighEvent).toHaveBeenCalledWith(
        expect.objectContaining({
          solo: { kind: 'reused', from_timestamp: '2025-12-01T00:00:00Z', gross: 10800, adjusted: true },
        })
      )
    );
  });

  it('sends a fresh Solo Ticket when the visitor enters a new one (Story 22)', async () => {
    const user = userEvent.setup();
    mockedApi.listTrucks.mockResolvedValue([truck]);
    mockedApi.listTrailers.mockResolvedValue([trailer]);
    mockedApi.getReusableSoloTicket.mockResolvedValue(null);
    mockedApi.createWeighEvent.mockResolvedValue(okEvent);

    renderPage();
    await pickProfilesAndFillCombined(user);

    expect(screen.getByText(/No reusable Solo weight/)).toBeInTheDocument();
    await user.click(screen.getByLabelText('Enter a new Solo Ticket'));
    await user.type(screen.getByLabelText('Solo Steer Axle (lb)'), '4300');
    await user.type(screen.getByLabelText('Solo Drive Axle (lb)'), '6200');
    await user.type(screen.getByLabelText('Solo Gross Weight (lb)'), '10500');
    await user.click(screen.getByRole('button', { name: 'See results' }));

    await waitFor(() =>
      expect(mockedApi.createWeighEvent).toHaveBeenCalledWith(
        expect.objectContaining({
          solo: expect.objectContaining({ kind: 'fresh', steer: 4300, drive: 6200, gross: 10500 }),
        })
      )
    );
  });

  it('shows a confirm step on a 409 mismatched Reweigh Reference, then resubmits with confirm_solo_link (Story 23)', async () => {
    const user = userEvent.setup();
    mockedApi.listTrucks.mockResolvedValue([truck]);
    mockedApi.listTrailers.mockResolvedValue([trailer]);
    mockedApi.getReusableSoloTicket.mockResolvedValue(null);
    mockedApi.createWeighEvent
      .mockRejectedValueOnce(new ApiError(409, { reason: 'solo_link_unconfirmed' }))
      .mockResolvedValueOnce(okEvent);

    renderPage();
    await pickProfilesAndFillCombined(user);
    await user.click(screen.getByLabelText('Enter a new Solo Ticket'));
    await user.type(screen.getByLabelText('Solo Steer Axle (lb)'), '4300');
    await user.type(screen.getByLabelText('Solo Drive Axle (lb)'), '6200');
    await user.type(screen.getByLabelText('Solo Gross Weight (lb)'), '10500');
    await user.click(screen.getByRole('button', { name: 'See results' }));

    expect(await screen.findByText('Confirm Solo Ticket link')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Yes, they belong together' }));

    await waitFor(() => expect(mockedApi.createWeighEvent).toHaveBeenCalledTimes(2));
    const secondCall = mockedApi.createWeighEvent.mock.calls[1][0];
    expect(secondCall.confirm_solo_link).toBe(true);
    expect(secondCall.solo).not.toBeNull();
  });

  it('resubmits with solo: null when the confirm step is declined (Story 24)', async () => {
    const user = userEvent.setup();
    mockedApi.listTrucks.mockResolvedValue([truck]);
    mockedApi.listTrailers.mockResolvedValue([trailer]);
    mockedApi.getReusableSoloTicket.mockResolvedValue(null);
    mockedApi.createWeighEvent
      .mockRejectedValueOnce(new ApiError(409, { reason: 'solo_link_unconfirmed' }))
      .mockResolvedValueOnce(okEvent);

    renderPage();
    await pickProfilesAndFillCombined(user);
    await user.click(screen.getByLabelText('Enter a new Solo Ticket'));
    await user.type(screen.getByLabelText('Solo Steer Axle (lb)'), '4300');
    await user.type(screen.getByLabelText('Solo Drive Axle (lb)'), '6200');
    await user.type(screen.getByLabelText('Solo Gross Weight (lb)'), '10500');
    await user.click(screen.getByRole('button', { name: 'See results' }));

    expect(await screen.findByText('Confirm Solo Ticket link')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'No, save Combined Ticket only' }));

    await waitFor(() => expect(mockedApi.createWeighEvent).toHaveBeenCalledTimes(2));
    const secondCall = mockedApi.createWeighEvent.mock.calls[1][0];
    expect(secondCall.solo).toBeNull();
  });
});
