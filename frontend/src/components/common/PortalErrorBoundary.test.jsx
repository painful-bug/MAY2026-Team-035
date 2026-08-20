import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import PortalErrorBoundary from './PortalErrorBoundary';

// A page that crashes on first render and recovers on the next one — the shape
// of the real defect this boundary was built for, where a transient payload
// (the snapshot 500) made the first render throw and a remount succeed.
function makeFlakyPage() {
  const state = { shouldThrow: true };
  function FlakyPage() {
    if (state.shouldThrow) throw new Error('render exploded');
    return <p>The page content</p>;
  }
  return { state, FlakyPage };
}

describe('PortalErrorBoundary', () => {
  it('contains a render error to a panel instead of blanking the tree', () => {
    // React logs caught render errors; the noise is expected here.
    vi.spyOn(console, 'error').mockImplementation(() => {});
    const { FlakyPage } = makeFlakyPage();

    render(
      <MemoryRouter>
        <nav>Portal chrome</nav>
        <PortalErrorBoundary>
          <FlakyPage />
        </PortalErrorBoundary>
      </MemoryRouter>
    );

    // The chrome outside the boundary survives, and the panel replaces only
    // the failed subtree.
    expect(screen.getByText('Portal chrome')).toBeInTheDocument();
    expect(screen.getByText('Something went wrong here.')).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: 'Try again' })
    ).toBeInTheDocument();
  });

  it('remounts the subtree when Try again is pressed', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    const user = userEvent.setup();
    const { state, FlakyPage } = makeFlakyPage();

    render(
      <MemoryRouter>
        <PortalErrorBoundary>
          <FlakyPage />
        </PortalErrorBoundary>
      </MemoryRouter>
    );
    expect(screen.getByText('Something went wrong here.')).toBeInTheDocument();

    state.shouldThrow = false;
    await user.click(screen.getByRole('button', { name: 'Try again' }));

    expect(screen.getByText('The page content')).toBeInTheDocument();
    expect(
      screen.queryByText('Something went wrong here.')
    ).not.toBeInTheDocument();
  });
});
