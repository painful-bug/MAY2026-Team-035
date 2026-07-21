import React from 'react';
import ConfirmationFooter from './ConfirmationFooter.jsx';
import ModalLayout from './ModalLayout.jsx';

export default function ConfirmationDialog({
  title,
  description,
  confirmLabel,
  confirmingLabel,
  isSubmitting,
  submissionError,
  onClose,
  onConfirm,
  tone = 'danger',
  children,
}) {
  return (
    <ModalLayout
      title={title}
      description={description}
      onClose={onClose}
      isBusy={isSubmitting}
      maxWidth="max-w-lg"
    >
      <form onSubmit={onConfirm} noValidate className="space-y-5">
        {submissionError && (
          <div
            role="alert"
            className="rounded-xl border border-rose-100 bg-rose-50 px-4 py-3 text-xs font-semibold text-rose-700"
          >
            {submissionError}
          </div>
        )}
        {children}
        <ConfirmationFooter
          onCancel={onClose}
          isSubmitting={isSubmitting}
          confirmLabel={confirmLabel}
          confirmingLabel={confirmingLabel}
          tone={tone}
        />
      </form>
    </ModalLayout>
  );
}
