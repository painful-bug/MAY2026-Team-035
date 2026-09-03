import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { GateModal } from './Primitives.jsx';

// Pins the portal contract for the gate sheet every security screen shares.
// SecurityLayout's <main> carries no animation today, so this overlay was
// never trapped the way the admin and resident ones were (`animate-fade-in`'s
// fill-forwards opacity animation keeps <main> a permanent stacking context)
// — the portal to document.body is what keeps that true if anyone ever
// animates the layout.

describe('GateModal portal contract', () => {
  it('portals the dialog to document.body with a full-cover overlay', () => {
    render(
      <GateModal title="Log an incident" onClose={vi.fn()}>
        <p>form body</p>
      </GateModal>
    );

    const dialog = screen.getByRole('dialog', { name: 'Log an incident' });
    expect(dialog.parentElement).toBe(document.body);
    expect(dialog.className).toContain('fixed inset-0');
    expect(dialog.className).toContain('z-[999]');
    // The panel scrolls internally instead of clipping.
    const panel = dialog.firstElementChild;
    expect(panel.className).toContain('overflow-y-auto');
    expect(panel.className).toContain('max-h-[90vh]');
  });

  it('keeps escape and backdrop-click closing behavior', () => {
    const onClose = vi.fn();
    render(
      <GateModal title="Log an incident" onClose={onClose}>
        <p>form body</p>
      </GateModal>
    );

    fireEvent.keyDown(document, { key: 'Escape' });
    expect(onClose).toHaveBeenCalledTimes(1);

    fireEvent.mouseDown(screen.getByRole('dialog'));
    expect(onClose).toHaveBeenCalledTimes(2);
  });
});
