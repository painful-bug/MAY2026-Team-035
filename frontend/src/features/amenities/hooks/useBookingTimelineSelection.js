import { useAmenityBookingsStore } from '../store/useAmenityBookingsStore.js';

export const useBookingTimelineSelection = () => {
  const selectedSlot = useAmenityBookingsStore(
    (state) => state.selectedSlot
  );
  const selectedBooking = useAmenityBookingsStore(
    (state) => state.selectedBooking
  );
  const selectedState = useAmenityBookingsStore(
    (state) => state.selectedState
  );
  const selectSlot = useAmenityBookingsStore((state) => state.selectSlot);
  const selectBooking = useAmenityBookingsStore(
    (state) => state.selectBooking
  );
  const clearSelection = useAmenityBookingsStore(
    (state) => state.clearSelection
  );

  return {
    selectedSlot,
    selectedBooking,
    selectedState,
    selectSlot,
    selectBooking,
    clearSelection,
  };
};
