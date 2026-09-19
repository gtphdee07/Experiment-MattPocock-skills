import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import ProtectedRoute from './ProtectedRoute';
import { AuthProvider } from './AuthContext';
import * as api from '../api';

vi.mock('../api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api')>();
  return { ...actual, getMe: vi.fn(), setUnauthorizedHandler: actual.setUnauthorizedHandler };
});

const mockedApi = vi.mocked(api);

function renderProtected(initialEntry = '/garage') {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<div>Login page</div>} />
          <Route
            path="/garage"
            element={
              <ProtectedRoute>
                <div>Garage page</div>
              </ProtectedRoute>
            }
          />
        </Routes>
      </AuthProvider>
    </MemoryRouter>
  );
}

describe('ProtectedRoute', () => {
  it('redirects to /login when there is no valid session (Story 8)', async () => {
    mockedApi.getMe.mockRejectedValue(new Error('401'));
    renderProtected();
    expect(await screen.findByText('Login page')).toBeInTheDocument();
  });

  it('renders the protected content once a session is confirmed', async () => {
    mockedApi.getMe.mockResolvedValue({
      id: 1,
      email: 'a@example.com',
      is_active: true,
      is_verified: true,
      is_superuser: false,
      created_at: 'now',
    });
    renderProtected();
    expect(await screen.findByText('Garage page')).toBeInTheDocument();
  });
});
