import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import Calculator from './Calculator';
import { AuthProvider } from '../auth/AuthContext';
import * as api from '../api';
import type { Account } from '../types';

vi.mock('../api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api')>();
  return { ...actual, getMe: vi.fn() };
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

function renderCalculator() {
  return render(
    <MemoryRouter initialEntries={['/']}>
      <AuthProvider>
        <Calculator />
      </AuthProvider>
    </MemoryRouter>
  );
}

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
    renderCalculator();

    expect(await screen.findByRole('link', { name: 'Garage' })).toHaveAttribute('href', '/garage');
    expect(screen.getByRole('link', { name: 'History' })).toHaveAttribute('href', '/weigh-events');
    expect(screen.getByText('addie@example.com')).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Log in' })).not.toBeInTheDocument();
  });
});
