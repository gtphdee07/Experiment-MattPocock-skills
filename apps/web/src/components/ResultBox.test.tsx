import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import ResultBox from './ResultBox';
import type { CheckOut } from '../types';

describe('ResultBox', () => {
  it('shows the Unverified Value note on a check that still Passes (Story 26)', () => {
    const check: CheckOut = {
      label: 'GCWR',
      status: 'pass',
      actual: 18000,
      rating: 22000,
      note: 'Unverified Value - GCWR is manually entered, not backed by a photo or CAT Scale Ticket.',
    };
    render(<ResultBox check={check} />);
    expect(screen.getByText(/Unverified Value/)).toBeInTheDocument();
    expect(screen.getByText('Pass')).toBeInTheDocument();
  });

  it('shows the note for a Not Evaluated check', () => {
    const check: CheckOut = {
      label: 'Trailer GVWR',
      status: 'not_evaluated',
      actual: null,
      rating: null,
      note: 'No Solo Ticket on file.',
    };
    render(<ResultBox check={check} />);
    expect(screen.getByText('No Solo Ticket on file.')).toBeInTheDocument();
  });

  it('renders no note text when the check carries none', () => {
    const check: CheckOut = { label: 'Steer', status: 'pass', actual: 4300, rating: 5000, note: null };
    const { container } = render(<ResultBox check={check} />);
    expect(container.textContent).not.toMatch(/Unverified/);
  });
});
