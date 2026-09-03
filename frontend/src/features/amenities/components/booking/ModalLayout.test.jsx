import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import ModalLayout from './ModalLayout.jsx';

// Pins the stacking-context escape shared by every booking modal
// (BookingFormModal, ConfirmationDialog, BlockTimeModal,
// TransactionDetailsPanel). Rendered in place, this overlay sat inside a
// layout's `<main class="animate-fade-in">` — a fill-forwards opacity
// animation keeps <main> a stacking context forever, so the overlay's
// z-[999] was trapped below the sticky header's z-40. The portal to
// document.body is what makes the overlay immune; these tests are the
// contract that keeps it there.

describe('booking ModalLayout portal contract', () => {
  it('portals the overlay to document.body with top-anchored internal scroll', () => {
    render(
      <ModalLayout title="Book the clubhouse" onClose={vi.fn()}>
        <p>form body</p>
      </ModalLayout>
    );

    const dialog = screen.getByRole('dialog', { name: 'Book the clubhouse' });
    const overlay = dialog.parentElement;
    // The portal contract: the overlay hangs off <body>, not off the page
    // that opened it, so no ancestor stacking context can capture it again.
    expect(overlay.parentElement).toBe(document.body);
    expect(overlay.className).toContain('fixed inset-0');
    expect(overlay.className).toContain('z-[999]');
    // Top-anchored: a panel taller than the viewport clips at the bottom
    // into its own scrollbar, never at the title.
    expect(overlay.className).toContain('items-start');
    expect(dialog.className).toContain('overflow-y-auto');
    expect(dialog.className).toContain('max-h-[calc(100vh-4rem)]');
  });

  it('keeps escape and backdrop-click closing behavior', () => {
    const onClose = vi.fn();
    render(
      <ModalLayout title="Book the clubhouse" onClose={onClose}>
        <p>form body</p>
      </ModalLayout>
    );

    fireEvent.keyDown(document, { key: 'Escape' });
    expect(onClose).toHaveBeenCalledTimes(1);

    const overlay = screen.getByRole('dialog').parentElement;
    fireEvent.mouseDown(overlay);
    expect(onClose).toHaveBeenCalledTimes(2);
  });

  it('does not close while busy', () => {
    const onClose = vi.fn();
    render(
      <ModalLayout title="Book the clubhouse" onClose={onClose} isBusy>
        <p>form body</p>
      </ModalLayout>
    );

    fireEvent.keyDown(document, { key: 'Escape' });
    fireEvent.mouseDown(screen.getByRole('dialog').parentElement);
    expect(onClose).not.toHaveBeenCalled();
  });
});
