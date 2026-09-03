import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import Notices from './Notices';

// Pins the stacking-context escape for the post-notice modal. Rendered in
// place, it sat inside AdminLayout's `<main class="animate-fade-in">` — a
// fill-forwards opacity animation keeps <main> a stacking context forever,
// so the overlay's z-[999] was trapped below the sticky header's z-40. The
// portal to document.body is what makes the overlay immune.

const mocks = vi.hoisted(() => ({ state: {} }));

// `useApp` is selector-based now: every call site passes a one-key selector,
// so the mock has to apply it (a bare object would hand the component the
// whole state where it expects one field).
vi.mock('../../store/useApp', () => ({
  useApp: (selector) => (selector ? selector(mocks.state) : mocks.state),
}));
vi.mock('../../lib/api/client', () => ({ api: vi.fn() }));

beforeEach(() => {
  mocks.state = { notices: [], showToast: vi.fn() };
});

describe('post-notice modal portal contract', () => {
  it('portals the dialog to document.body with a full-cover overlay', async () => {
    const user = userEvent.setup();
    render(<Notices />);

    await user.click(screen.getByRole('button', { name: /post notice/i }));

    const dialog = screen.getByRole('dialog', { name: 'Post new notice' });
    expect(dialog.parentElement).toBe(document.body);
    expect(dialog.className).toContain('fixed inset-0');
    expect(dialog.className).toContain('z-[999]');
    // The panel scrolls internally on a short viewport instead of clipping.
    // `dvh`, not `vh`: the guard that landed on this panel independently
    // measures the dynamic viewport, so a mobile browser's collapsing URL bar
    // cannot push the panel's bottom out of reach. Kept as-is by the port.
    const panel = dialog.firstElementChild;
    expect(panel.className).toContain('overflow-y-auto');
    expect(panel.className).toContain('max-h-[calc(100dvh-2rem)]');
  });

  it('keeps the Cancel close behavior', async () => {
    const user = userEvent.setup();
    render(<Notices />);

    await user.click(screen.getByRole('button', { name: /post notice/i }));
    await user.click(screen.getByRole('button', { name: 'Cancel' }));

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });
});
