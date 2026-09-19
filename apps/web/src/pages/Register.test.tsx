import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import Register from './Register';
import { AppThemeProvider } from '../theme/ThemeContext';
import { AuthProvider } from '../auth/AuthContext';
import { ApiError } from '../api';
import * as api from '../api';

vi.mock('../api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api')>();
  return { ...actual, register: vi.fn(), getMe: vi.fn().mockRejectedValue(new Error('401')) };
});

const mockedApi = vi.mocked(api);

function renderRegister() {
  return render(
    <MemoryRouter initialEntries={['/register']}>
      <AuthProvider>
        <AppThemeProvider>
          <Register />
        </AppThemeProvider>
      </AuthProvider>
    </MemoryRouter>
  );
}

describe('Register', () => {
  it('shows a clear inline error for a duplicate email, keeping what was typed (Story 3)', async () => {
    const user = userEvent.setup();
    mockedApi.register.mockRejectedValue(new ApiError(400, 'REGISTER_USER_ALREADY_EXISTS'));
    renderRegister();

    await user.type(screen.getByLabelText('Email'), 'addie@example.com');
    await user.type(screen.getByLabelText('Password'), 'correct-horse-battery-staple');
    await user.click(screen.getByRole('button', { name: 'Register' }));

    expect(await screen.findByText(/already registered/i)).toBeInTheDocument();
    expect(screen.getByLabelText('Email')).toHaveValue('addie@example.com');
    expect(screen.getByLabelText('Password')).toHaveValue('correct-horse-battery-staple');
  });

  it('shows a clear inline error for a too-short password (Story 3)', async () => {
    const user = userEvent.setup();
    mockedApi.register.mockRejectedValue(
      new ApiError(400, { code: 'REGISTER_INVALID_PASSWORD', reason: 'Password should be at least 8 characters' })
    );
    renderRegister();

    await user.type(screen.getByLabelText('Email'), 'addie@example.com');
    await user.type(screen.getByLabelText('Password'), 'short');
    await user.click(screen.getByRole('button', { name: 'Register' }));

    expect(await screen.findByText(/at least 8 characters/i)).toBeInTheDocument();
    expect(screen.getByLabelText('Email')).toHaveValue('addie@example.com');
  });
});
