import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import AdminHome from './AdminHome';

// The trend chips: a literal "+2 this week" shipped with the demo and survived
// into the live app. They now read the snapshot's `weeklyNew` counts and must
// be correct on both sides of the parallel backend change — no chip for a
// missing field, no chip for zero, "+N this week" for a real count.

const mocks = vi.hoisted(() => ({ state: {} }));

vi.mock('../../store/useApp', () => ({ useApp: () => mocks.state }));

const baseState = () => ({
  users: [],
  pendingRequests: [],
  complaints: [],
  payments: [],
  activities: [],
  weeklyNew: null,
});

const renderPage = () =>
  render(
    <MemoryRouter>
      <AdminHome />
    </MemoryRouter>
  );

describe('admin dashboard pending approval rows', () => {
  // The demo-era card read `req.name` / `req.flat` / `req.tower`, keys that
  // never existed on the snapshot's snake_case view rows — the live app showed
  // "Flat undefined • Tower undefined". The rows carry applicant_name plus
  // requested_unit_code and, post-migration, the applicant's free-text claim.
  it('renders applicant names and residences without any undefined', () => {
    mocks.state = {
      ...baseState(),
      pendingRequests: [
        { id: 'r1', applicant_name: 'Asha Rao', requested_unit_code: 'C-505' },
        { id: 'r2', applicant_name: 'Vikram Shetty', requested_building_text: 'B', requested_unit_text: '204' },
        { id: 'r3', applicant_name: 'Meera Iyer' },
      ],
    };
    const { container } = renderPage();

    expect(screen.getByText('Asha Rao')).toBeInTheDocument();
    expect(screen.getByText('C-505')).toBeInTheDocument();
    expect(screen.getByText('Tower B · Flat 204')).toBeInTheDocument();
    expect(screen.getByText('Meera Iyer')).toBeInTheDocument();
    expect(screen.getByText('—')).toBeInTheDocument();
    expect(container.textContent).not.toContain('undefined');
  });
});

describe('admin dashboard trend chips', () => {
  it('renders no trend chip while the snapshot has no weeklyNew field', () => {
    mocks.state = baseState();
    renderPage();

    expect(screen.queryByText(/this week/)).not.toBeInTheDocument();
  });

  it('renders "+N this week" from weeklyNew and skips zero counts', () => {
    mocks.state = {
      ...baseState(),
      weeklyNew: { residents: 3, complaints: 0, visitorRequests: 0, bookings: 0 },
    };
    renderPage();

    expect(screen.getByText('+3 this week')).toBeInTheDocument();
    // complaints is 0 — exactly one chip on the page.
    expect(screen.getAllByText(/this week/)).toHaveLength(1);
  });

  it('renders the complaints chip from its own count', () => {
    mocks.state = {
      ...baseState(),
      weeklyNew: { residents: 0, complaints: 5, visitorRequests: 0, bookings: 0 },
    };
    renderPage();

    expect(screen.getByText('+5 this week')).toBeInTheDocument();
    expect(screen.getAllByText(/this week/)).toHaveLength(1);
  });
});
