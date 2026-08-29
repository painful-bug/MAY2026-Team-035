import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import AmenityFormModal from './AmenityFormModal.jsx';

// Pins the stacking-context escape for the add-amenity form. Rendered in
// place, it sat inside AdminLayout's `<main class="animate-fade-in">` — a
// fill-forwards opacity animation keeps <main> a stacking context forever,
// so the overlay's z-[999] was trapped below the sticky header's z-40. The
// portal to document.body is what makes the overlay immune; these tests are
// the contract that keeps it there.

describe('AmenityFormModal portal contract', () => {
  it('portals the overlay to document.body with top-anchored internal scroll', () => {
    render(
      <AmenityFormModal
        onClose={vi.fn()}
        onSubmit={vi.fn()}
        isSubmitting={false}
        submissionError={null}
      />
    );

    const dialog = screen.getByRole('dialog', { name: 'Add Amenity' });
    const overlay = dialog.parentElement;
    expect(overlay.parentElement).toBe(document.body);
    expect(overlay.className).toContain('fixed inset-0');
    expect(overlay.className).toContain('z-[999]');
    // Top-anchored: this form is taller than most viewports, and a centered
    // child taller than the viewport loses its top edge — the title.
    expect(overlay.className).toContain('items-start');
    expect(dialog.className).toContain('overflow-y-auto');
    expect(dialog.className).toContain('max-h-[calc(100vh-4rem)]');
  });

  it('keeps escape and backdrop-click closing behavior', () => {
    const onClose = vi.fn();
    render(
      <AmenityFormModal
        onClose={onClose}
        onSubmit={vi.fn()}
        isSubmitting={false}
        submissionError={null}
      />
    );

    fireEvent.keyDown(document, { key: 'Escape' });
    expect(onClose).toHaveBeenCalledTimes(1);

    fireEvent.mouseDown(screen.getByRole('dialog').parentElement);
    expect(onClose).toHaveBeenCalledTimes(2);
  });
});
