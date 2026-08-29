import React, { useEffect, useId } from 'react';
// Rendered through a portal to document.body. In place, this overlay sat
// inside a layout's `<main class="animate-fade-in">` — a fill-forwards opacity
// animation keeps <main> a stacking context forever, so `z-[999]` here was
// trapped at <main>'s own level and the sticky header's `z-40` painted above
// it. Same fix as the departments modals (Departments.jsx).
import { createPortal } from 'react-dom';

export default function ModalLayout({
  title,
  description,
  onClose,
  isBusy = false,
  maxWidth = 'max-w-2xl',
  children,
}) {
  const titleId = useId();

  useEffect(() => {
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    const handleEscape = (event) => {
      if (event.key === 'Escape' && !isBusy) {
        onClose();
      }
    };

    document.addEventListener('keydown', handleEscape);

    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener('keydown', handleEscape);
    };
  }, [isBusy, onClose]);

  const handleBackdropClick = (event) => {
    if (event.target === event.currentTarget && !isBusy) {
      onClose();
    }
  };

  // items-start, not items-center: a centered child taller than the viewport
  // loses its top edge — the title — so the panel anchors to the top and
  // scrolls internally inside the remaining height instead.
  return createPortal(
    <div
      className="fixed inset-0 z-[999] flex items-start justify-center bg-slate-900/60 px-4 py-8 backdrop-blur-sm animate-fade-in"
      onMouseDown={handleBackdropClick}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className={`max-h-[calc(100vh-4rem)] w-full ${maxWidth} overflow-y-auto rounded-3xl border border-slate-100 bg-white p-6 shadow-xl shadow-slate-100 animate-slide-up`}
      >
        <div className="mb-6 flex items-start justify-between gap-4">
          <div>
            <h2
              id={titleId}
              className="text-lg font-extrabold tracking-tight text-slate-900"
            >
              {title}
            </h2>
            {description && (
              <p className="mt-1 text-xs font-medium text-slate-400">
                {description}
              </p>
            )}
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={isBusy}
            className="text-xs font-bold text-slate-400 transition-colors hover:text-slate-700 disabled:cursor-not-allowed disabled:opacity-60"
          >
            Cancel
          </button>
        </div>

        {children}
      </div>
    </div>,
    document.body
  );
}
