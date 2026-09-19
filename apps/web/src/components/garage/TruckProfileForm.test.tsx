import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import TruckProfileForm from './TruckProfileForm';
import { AppThemeProvider } from '../../theme/ThemeContext';

function renderForm(onSubmit = vi.fn()) {
  render(
    <AppThemeProvider>
      <TruckProfileForm submitLabel="Add Truck" onSubmit={onSubmit} onCancel={vi.fn()} />
    </AppThemeProvider>
  );
  return { onSubmit };
}

describe('TruckProfileForm', () => {
  it('rejects a zero GVWR before submit (Story 15)', async () => {
    const user = userEvent.setup();
    const { onSubmit } = renderForm();

    await user.type(screen.getByLabelText('GVWR (lb)'), '0');
    await user.type(screen.getByLabelText('Front GAWR (lb)'), '4500');
    await user.type(screen.getByLabelText('Rear GAWR (lb)'), '6500');
    await user.click(screen.getByRole('button', { name: 'Add Truck' }));

    expect(await screen.findByText(/greater than zero/)).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it('rejects a negative rating before submit (Story 15)', async () => {
    const user = userEvent.setup();
    const { onSubmit } = renderForm();

    await user.type(screen.getByLabelText('GVWR (lb)'), '10000');
    await user.type(screen.getByLabelText('Front GAWR (lb)'), '-500');
    await user.type(screen.getByLabelText('Rear GAWR (lb)'), '6500');
    await user.click(screen.getByRole('button', { name: 'Add Truck' }));

    expect(await screen.findByText(/greater than zero/)).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it('submits a valid payload, omitting an optional blank GCWR/Nickname as null', async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    renderForm(onSubmit);

    await user.type(screen.getByLabelText('GVWR (lb)'), '10000');
    await user.type(screen.getByLabelText('Front GAWR (lb)'), '4500');
    await user.type(screen.getByLabelText('Rear GAWR (lb)'), '6500');
    await user.click(screen.getByRole('button', { name: 'Add Truck' }));

    expect(onSubmit).toHaveBeenCalledWith({
      gvwr: 10000,
      front_gawr: 4500,
      rear_gawr: 6500,
      gcwr: null,
      nickname: null,
    });
  });
});
