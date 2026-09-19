import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import Login from './Login';
import { AppThemeProvider } from '../theme/ThemeContext';
import { AuthProvider } from '../auth/AuthContext';
import * as api from '../api';

vi.mock('../api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api')>();
  return { ...actual, login: vi.fn(), getMe: vi.fn().mockRejectedValue(new Error('401')) };
});

const mockedApi = vi.mocked(api);

function renderLogin() {
  return render(
    <MemoryRouter initialEntries={['/login']}>
      <AuthProvider>
        <AppThemeProvider>
          <Login />
        </AppThemeProvider>
      </AuthProvider>
    </MemoryRouter>
  );
}

describe('Login', () => {
  it('shows one generic message for a wrong password (Story 5)', async () => {
    const user = userEvent.setup();
    mockedApi.login.mockRejectedValue(new Error('bad credentials'));
    renderLogin();

    await user.type(screen.getByLabelText('Email'), 'addie@example.com');
    await user.type(screen.getByLabelText('Password'), 'wrong-password');
    await user.click(screen.getByRole('button', { name: 'Log in' }));

    const alert = await screen.findByRole('alert');
    expect(alert.textContent).toMatch(/not valid/i);
  });

  it('shows the identical generic message for an unregistered email (Story 5)', async () => {
    const user = userEvent.setup();
    mockedApi.login.mockRejectedValue(new Error('bad credentials'));
    renderLogin();

    await user.type(screen.getByLabelText('Email'), 'nobody@example.com');
    await user.type(screen.getByLabelText('Password'), 'whatever123');
    await user.click(screen.getByRole('button', { name: 'Log in' }));

    const alert = await screen.findByRole('alert');
    expect(alert.textContent).toMatch(/not valid/i);
  });
});
