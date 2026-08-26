import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import Header from './Header';

// The residency chip reads the signed-in member's unit from GET /auth/session,
// so it does not wait for the large dashboard snapshot. Missing residency data
// hides the chip instead of rendering placeholder punctuation.

const mocks = vi.hoisted(() => ({ state: {} }));

vi.mock('../../store/useApp', () => ({
  useApp: (selector) => (selector ? selector(mocks.state) : mocks.state),
}));

// The bell polls GET /notifications; irrelevant to the chip under test.
vi.mock('../notifications/NotificationBell', () => ({ default: () => null }));

const baseState = () => ({
  currentUser: { id: 'p1', name: 'Asha Rao', role: 'Resident' },
  notices: [],
  visitors: [],
  complaints: [],
  activities: [],
  searchQuery: '',
  setSearchQuery: vi.fn(),
});

describe('header residency chip', () => {
  it('shows the real flat and tower from the session user', () => {
    mocks.state = {
      ...baseState(),
      currentUser: {
        id: 'p1', name: 'Asha Rao', role: 'Resident', flat: 'B-1204', tower: 'Emerald',
      },
    };
    render(<Header onMenuClick={() => {}} />);

    expect(screen.getByText('Flat B-1204 • Tower Emerald')).toBeInTheDocument();
  });

  it('hides the chip when the member has no unit residency', () => {
    // The session maps a missing active residency to placeholders/null; those
    // must render no chip rather than an em-dash label.
    mocks.state = {
      ...baseState(),
      currentUser: { id: 'p1', name: 'Asha Rao', role: 'Admin', flat: '—', tower: null },
    };
    render(<Header onMenuClick={() => {}} />);

    expect(screen.queryByText(/Flat/)).not.toBeInTheDocument();
    expect(screen.queryByText(/—/)).not.toBeInTheDocument();
  });

  it('shows the unit without a tower for a standalone home', () => {
    mocks.state = {
      ...baseState(),
      currentUser: {
        id: 'p1', name: 'Asha Rao', role: 'Resident', flat: 'Villa 7', tower: null,
      },
    };
    render(<Header onMenuClick={() => {}} />);

    expect(screen.getByText('Flat Villa 7')).toBeInTheDocument();
    expect(screen.queryByText(/Tower/)).not.toBeInTheDocument();
  });

  it('hides the chip when the session has no residency labels', () => {
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
