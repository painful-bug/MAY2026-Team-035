import { useAmenityBookingsStore } from '../store/useAmenityBookingsStore.js';

export const useAmenityBookingWorkflow = () => {
  const residents = useAmenityBookingsStore((state) => state.residents);
  const isResidentsLoading = useAmenityBookingsStore(
    (state) => state.isResidentsLoading
  );
  const isSubmitting = useAmenityBookingsStore(
    (state) => state.isSubmitting
  );
  const modalError = useAmenityBookingsStore((state) => state.modalError);
  const isBookingModalOpen = useAmenityBookingsStore(
    (state) => state.isBookingModalOpen
  );
  const isEditBookingModalOpen = useAmenityBookingsStore(
    (state) => state.isEditBookingModalOpen
  );
  const isCancelBookingDialogOpen = useAmenityBookingsStore(
    (state) => state.isCancelBookingDialogOpen
  );
  const isMaintenanceModalOpen = useAmenityBookingsStore(
    (state) => state.isMaintenanceModalOpen
  );
  const openBookingModal = useAmenityBookingsStore(
    (state) => state.openBookingModal
  );
  const openMaintenanceModal = useAmenityBookingsStore(
    (state) => state.openMaintenanceModal
  );
  const closeModal = useAmenityBookingsStore((state) => state.closeModal);
  const openCancelBookingDialog = useAmenityBookingsStore(
    (state) => state.openCancelBookingDialog
  );
  const closeCancelBookingDialog = useAmenityBookingsStore(
    (state) => state.closeCancelBookingDialog
  );
  const createBooking = useAmenityBookingsStore(
    (state) => state.createBooking
  );
  const createBlockedSlot = useAmenityBookingsStore(
    (state) => state.createBlockedSlot
  );
  const updateBooking = useAmenityBookingsStore(
    (state) => state.updateBooking
  );
  const cancelBooking = useAmenityBookingsStore(
    (state) => state.cancelBooking
  );

  return {
    residents,
    isResidentsLoading,
    isSubmitting,
    modalError,
    isBookingModalOpen,
    isEditBookingModalOpen,
    isCancelBookingDialogOpen,
    isMaintenanceModalOpen,
    openBookingModal,
    openMaintenanceModal,
    closeModal,
    openCancelBookingDialog,
    closeCancelBookingDialog,
    createBooking,
    createBlockedSlot,
    updateBooking,
    cancelBooking,
  };
};
