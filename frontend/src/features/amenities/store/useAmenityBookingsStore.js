import { create } from 'zustand';
import { useAppStore } from '../../../store/appStore.js';
import { useAuthStore } from '../../../store/authStore.js';
import { BOOKING_TIMELINE_STATE } from '../constants/bookingTimelineStates.js';
import {
  approveAmenityBookingRequest,
  cancelAmenityBooking,
  createAmenityBlockedSlot,
  createAmenityBooking,
  getAmenityBookings,
  getAmenityApprovalRequests,
  getBookableResidents,
  rejectAmenityBookingRequest,
  sortAmenityBookings,
  updateAmenityBooking,
  validateBookingSlot,
} from '../services/amenityBookingsService.js';

const getErrorMessage = (error) =>
  error instanceof Error ? error.message : 'Unable to load bookings.';

const getRequestKey = (amenityId, date) => `${amenityId}:${date}`;

const loadResidentsIfNeeded = async (set, get) => {
  if (get().residents.length > 0) {
    return;
  }

  set({ isResidentsLoading: true });
  try {
    const residents = await getBookableResidents();
    set({ residents, isResidentsLoading: false });
  } catch (error) {
    set({
      modalError: getErrorMessage(error),
      isResidentsLoading: false,
    });
  }
};

export const useAmenityBookingsStore = create((set, get) => ({
  bookings: [],
  residents: [],
  requestKey: null,
  isLoading: false,
  isResidentsLoading: false,
  isSubmitting: false,
  error: null,
  modalError: null,
  isBookingModalOpen: false,
  isEditBookingModalOpen: false,
  isCancelBookingDialogOpen: false,
  isMaintenanceModalOpen: false,
  selectedDate: null,
  selectedSlot: null,
  selectedBooking: null,
  selectedState: null,
  approvalRequests: [],
  approvalRequestKey: null,
  isApprovalsLoading: false,
  approvalsError: null,
  approvingBookingId: null,
  rejectingBookingId: null,
  rejectionError: null,

  selectSlot: (slot) =>
    set({
      selectedDate: slot.date,
      selectedSlot: slot,
      selectedBooking: null,
      selectedState: BOOKING_TIMELINE_STATE.AVAILABLE,
    }),

  selectBooking: async (booking) => {
    const canEdit = booking.state === BOOKING_TIMELINE_STATE.BOOKED;

    set({
      selectedDate: booking.date,
      selectedSlot: null,
      selectedBooking: booking,
      selectedState: booking.state,
      isBookingModalOpen: false,
      isEditBookingModalOpen: canEdit,
      isCancelBookingDialogOpen: false,
      isMaintenanceModalOpen: false,
      modalError: null,
    });

    if (canEdit) {
      await loadResidentsIfNeeded(set, get);
    }
  },

  clearSelection: () =>
    set({
      selectedSlot: null,
      selectedBooking: null,
      selectedState: null,
    }),

  syncForceCancelledBooking: (booking) =>
    set((state) => ({
      bookings: state.bookings.filter(
        (currentBooking) => currentBooking.id !== booking.id
      ),
      approvalRequests: state.approvalRequests.map((request) =>
        request.id === booking.id ? { ...request, ...booking } : request
      ),
      selectedBooking:
        state.selectedBooking?.id === booking.id
          ? null
          : state.selectedBooking,
      selectedState:
        state.selectedBooking?.id === booking.id
          ? null
          : state.selectedState,
    })),

  openBookingModal: async () => {
    const state = get();

    if (
      !state.selectedSlot ||
      state.selectedState !== BOOKING_TIMELINE_STATE.AVAILABLE
    ) {
      return false;
    }

    set({
      isBookingModalOpen: true,
      isEditBookingModalOpen: false,
      isCancelBookingDialogOpen: false,
      isMaintenanceModalOpen: false,
      modalError: null,
    });

    await loadResidentsIfNeeded(set, get);

    return true;
  },

  openMaintenanceModal: () =>
    set({
      isBookingModalOpen: false,
      isEditBookingModalOpen: false,
      isCancelBookingDialogOpen: false,
      isMaintenanceModalOpen: true,
      modalError: null,
    }),

  openCancelBookingDialog: () => {
    const state = get();

    if (
      !state.selectedBooking ||
      state.selectedBooking.state !== BOOKING_TIMELINE_STATE.BOOKED
    ) {
      return false;
    }

    set({
      isCancelBookingDialogOpen: true,
      modalError: null,
    });
    return true;
  },

  closeCancelBookingDialog: () => {
    if (get().isSubmitting) {
      return;
    }

    set({
      isCancelBookingDialogOpen: false,
      modalError: null,
    });
  },

  closeModal: () => {
    if (get().isSubmitting) {
      return;
    }

    set({
      isBookingModalOpen: false,
      isEditBookingModalOpen: false,
      isCancelBookingDialogOpen: false,
      isMaintenanceModalOpen: false,
      modalError: null,
    });
  },

  validateSlotAvailability: async (slotData) =>
    validateBookingSlot(slotData),

  createBooking: async (bookingData) => {
    set({ isSubmitting: true, modalError: null });

    try {
      const booking = await createAmenityBooking(bookingData);
      set((state) => ({
        bookings: sortAmenityBookings([...state.bookings, booking]),
        selectedSlot: null,
        selectedBooking: booking,
        selectedState: BOOKING_TIMELINE_STATE.BOOKED,
        isSubmitting: false,
        isBookingModalOpen: false,
        isEditBookingModalOpen: false,
      }));
      const appStore = useAppStore.getState();
      appStore.showToast('Booking created successfully', 'success');
      appStore.addActivity(
        `Admin created ${booking.bookingTitle} for ${booking.residentName}`,
        'general'
      );
      return booking;
    } catch (error) {
      set({
        isSubmitting: false,
        modalError: getErrorMessage(error),
      });
      return null;
    }
  },

  createBlockedSlot: async (blockedSlotData) => {
    set({ isSubmitting: true, modalError: null });

    try {
      const blockedSlot = await createAmenityBlockedSlot(blockedSlotData);
      set((state) => ({
        bookings: sortAmenityBookings([...state.bookings, blockedSlot]),
        selectedSlot: null,
        selectedBooking: blockedSlot,
        selectedState: BOOKING_TIMELINE_STATE.BLOCKED,
        isSubmitting: false,
        isMaintenanceModalOpen: false,
      }));
      const appStore = useAppStore.getState();
      appStore.showToast('Time blocked successfully', 'success');
      appStore.addActivity(
        `Admin blocked ${blockedSlot.bookingTitle} for ${blockedSlot.department}`,
        'general'
      );
      return blockedSlot;
    } catch (error) {
      set({
        isSubmitting: false,
        modalError: getErrorMessage(error),
      });
      return null;
    }
  },

  updateBooking: async (bookingId, bookingData) => {
    set({ isSubmitting: true, modalError: null });

    try {
      const booking = await updateAmenityBooking(bookingId, bookingData);
      set((state) => ({
        bookings:
          booking.date === state.selectedDate
            ? sortAmenityBookings(
                state.bookings.map((currentBooking) =>
                  currentBooking.id === booking.id
                    ? booking
                    : currentBooking
                )
              )
            : state.bookings.filter(
                (currentBooking) => currentBooking.id !== booking.id
              ),
        selectedSlot: null,
        selectedBooking: booking,
        selectedState: BOOKING_TIMELINE_STATE.BOOKED,
        isSubmitting: false,
        isEditBookingModalOpen: false,
      }));
      const appStore = useAppStore.getState();
      appStore.showToast('Booking updated successfully', 'success');
      appStore.addActivity(
        `Admin updated ${booking.bookingTitle} for ${booking.residentName}`,
        'general'
      );
      return booking;
    } catch (error) {
      set({
        isSubmitting: false,
        modalError: getErrorMessage(error),
      });
      return null;
    }
  },

  cancelBooking: async (bookingId, cancellationData) => {
    set({ isSubmitting: true, modalError: null });

    try {
      const booking = await cancelAmenityBooking(
        bookingId,
        cancellationData
      );
      set((state) => ({
        bookings: state.bookings.filter(
          (currentBooking) => currentBooking.id !== booking.id
        ),
        selectedSlot: null,
        selectedBooking: booking,
        selectedState: BOOKING_TIMELINE_STATE.BOOKED,
        isSubmitting: false,
        isEditBookingModalOpen: false,
        isCancelBookingDialogOpen: false,
      }));
      const appStore = useAppStore.getState();
      appStore.showToast('Booking cancelled successfully', 'success');
      appStore.addActivity(
        `Admin cancelled ${booking.bookingTitle} for ${booking.residentName}`,
        'general'
      );
      return booking;
    } catch (error) {
      set({
        isSubmitting: false,
        modalError: getErrorMessage(error),
      });
      return null;
    }
  },

  fetchApprovalRequests: async (amenityId) => {
    set({
      approvalRequests: [],
      approvalRequestKey: amenityId,
      isApprovalsLoading: true,
      approvalsError: null,
      approvingBookingId: null,
      rejectingBookingId: null,
      rejectionError: null,
    });

    try {
      const approvalRequests = await getAmenityApprovalRequests(amenityId);
      set((state) =>
        state.approvalRequestKey === amenityId
          ? { approvalRequests, isApprovalsLoading: false }
          : state
      );
      return approvalRequests;
    } catch (error) {
      set((state) =>
        state.approvalRequestKey === amenityId
          ? {
              approvalRequests: [],
              isApprovalsLoading: false,
              approvalsError: getErrorMessage(error),
            }
          : state
      );
      return [];
    }
  },

  approveBookingRequest: async (bookingId) => {
    set({ approvingBookingId: bookingId, approvalsError: null });

    try {
      const booking = await approveAmenityBookingRequest(bookingId);
      set((state) => ({
        approvalRequests: state.approvalRequests.map((request) =>
          request.id === booking.id ? booking : request
        ),
        approvingBookingId: null,
      }));
      const appStore = useAppStore.getState();
      appStore.showToast('Booking request approved', 'success');
      appStore.addActivity(
        `Admin approved ${booking.bookingTitle} for ${booking.residentName}`,
        'general'
      );
      return booking;
    } catch (error) {
      set({
        approvingBookingId: null,
        approvalsError: getErrorMessage(error),
      });
      return null;
    }
  },

  clearRejectionError: () => set({ rejectionError: null }),

  rejectBookingRequest: async (bookingId, rejectionData) => {
    set({ rejectingBookingId: bookingId, rejectionError: null });

    try {
      const currentUser = useAuthStore.getState().currentUser;
      const booking = await rejectAmenityBookingRequest(bookingId, {
        ...rejectionData,
        rejectedBy: currentUser?.id ?? 'admin',
      });
      set((state) => ({
        approvalRequests: state.approvalRequests.map((request) =>
          request.id === booking.id ? booking : request
        ),
        rejectingBookingId: null,
      }));
      const appStore = useAppStore.getState();
      appStore.showToast('Booking request rejected', 'success');
      appStore.addActivity(
        `Admin rejected ${booking.bookingTitle} for ${booking.residentName}`,
        'general'
      );
      return booking;
    } catch (error) {
      set({
        rejectingBookingId: null,
        rejectionError: getErrorMessage(error),
      });
      return null;
    }
  },

  fetchBookings: async (amenityId, date) => {
    const requestKey = getRequestKey(amenityId, date);

    set({
      bookings: [],
      requestKey,
      isLoading: true,
      error: null,
      modalError: null,
      isBookingModalOpen: false,
      isEditBookingModalOpen: false,
      isCancelBookingDialogOpen: false,
      isMaintenanceModalOpen: false,
      selectedDate: date,
      selectedSlot: null,
      selectedBooking: null,
      selectedState: null,
    });

    try {
      const bookings = await getAmenityBookings(amenityId, date);
      set((state) =>
        state.requestKey === requestKey
          ? { bookings, isLoading: false }
          : state
      );
      return bookings;
    } catch (error) {
      set((state) =>
        state.requestKey === requestKey
          ? {
              bookings: [],
              isLoading: false,
              error: getErrorMessage(error),
            }
          : state
      );
      return [];
    }
  },
}));
