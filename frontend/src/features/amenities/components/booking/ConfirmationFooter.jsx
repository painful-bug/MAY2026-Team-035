import React from 'react';
import ModalFooter from './ModalFooter.jsx';

export default function ConfirmationFooter({
  onCancel,
  isSubmitting,
  confirmLabel,
  confirmingLabel,
  tone = 'danger',
}) {
  return (
    <ModalFooter
      onCancel={onCancel}
      isSubmitting={isSubmitting}
      submitLabel={confirmLabel}
      submittingLabel={confirmingLabel}
      submitTone={tone}
    />
  );
}
