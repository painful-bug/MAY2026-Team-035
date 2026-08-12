import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import Header from './Header';

// The residency chip used to read `currentUser.flat`/`tower`, which the auth
// session hard-codes to '—' — every member saw "Flat — • Tower —". It now
// reads the signed-in member's own row from the snapshot's `users` projection
// (real unit/building data) and hides entirely when there is no active
// residency to show.

const mocks = vi.hoisted(() => ({ state: {} }));

vi.mock('../../store/useApp', () => ({ useApp: () => mocks.state }));

// The bell polls GET /notifications; irrelevant to the chip under test.
vi.mock('../notifications/NotificationBell', () => ({ default: () => null }));

const baseState = () => ({
  currentUser: { id: 'p1', name: 'Asha Rao', role: 'Resident' },
  users: [],
  notices: [],
  visitors: [],
  complaints: [],
  activities: [],
  searchQuery: '',
  setSearchQuery: vi.fn(),
});

describe('header residency chip', () => {
  it('shows the real flat and tower from the snapshot users projection', () => {
    mocks.state = {
      ...baseState(),
      users: [{ id: 'p1', flat: 'B-1204', tower: 'Emerald' }],
    };
    render(<Header onMenuClick={() => {}} />);

    expect(screen.getByText('Flat B-1204 • Tower Emerald')).toBeInTheDocument();
  });

  it('hides the chip when the member has no unit residency', () => {
    // The snapshot uses the same '—' placeholder for members without an
    // active residency (a pure admin, typically); both that and a missing row
    // must render no chip rather than an em-dash label.
    mocks.state = {
      ...baseState(),
      currentUser: { id: 'p1', name: 'Asha Rao', role: 'Admin' },
      users: [{ id: 'p1', flat: '—', tower: '—' }],
    };
    render(<Header onMenuClick={() => {}} />);

    expect(screen.queryByText(/Flat/)).not.toBeInTheDocument();
    expect(screen.queryByText(/—/)).not.toBeInTheDocument();
  });

  it('hides the chip while the snapshot has not loaded', () => {
    mocks.state = baseState();
    render(<Header onMenuClick={() => {}} />);

    expect(screen.queryByText(/Flat/)).not.toBeInTheDocument();
  });

  it('keeps the duty label for security staff', () => {
    mocks.state = {
      ...baseState(),
      currentUser: { id: 'p2', name: 'Gate Guard', role: 'Security' },
    };
    render(<Header onMenuClick={() => {}} />);

    expect(screen.getByText('On duty')).toBeInTheDocument();
  });
});
