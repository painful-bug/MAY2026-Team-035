import { genId } from '../../lib/ids';
import { initialAmenities, initialBookings } from '../../data/amenities';
import { useAuthStore } from '../authStore';

// Amenities + their bookings live together — resident booking and admin
// management both operate on the same pair.
export const createAmenitiesSlice = (set, get) => ({
  amenities: initialAmenities,
  bookings: initialBookings,

  bookAmenity: (bookingData) => {
    const currentUser = useAuthStore.getState().currentUser;
    const selectedAmenity = get().amenities.find((a) => a.id === bookingData.amenityId);
    const newBooking = {
      id: genId('b'),
      amenityId: bookingData.amenityId,
      amenityName: selectedAmenity ? selectedAmenity.name : 'Amenity',
      bookedBy: currentUser?.name || 'Aakash S.',
      userId: currentUser?.id || 'u1',
      flat: currentUser ? `${currentUser.flat}` : 'B-1204',
      date: bookingData.date,
      timeSlot: bookingData.timeSlot,
      status: 'Confirmed',
    };
    set((s) => ({ bookings: [...s.bookings, newBooking] }));
    get().showToast(`Successfully booked ${newBooking.amenityName}!`, 'success');
    get().addActivity(`You booked ${newBooking.amenityName} for ${bookingData.date}`, 'general');
  },

  addAmenity: (amenityData) => {
    const newAmenity = {
      id: genId('a'),
      name: amenityData.name,
      timing: amenityData.timing || '06:00 AM - 10:00 PM',
      capacity: Number(amenityData.capacity) || 50,
      status: 'Open',
      description: amenityData.description || '',
    };
    set((s) => ({ amenities: [...s.amenities, newAmenity] }));
    get().showToast(`Amenity "${amenityData.name}" added successfully`, 'success');
    get().addActivity(`Admin added new amenity: "${amenityData.name}"`, 'general');
  },

  deleteAmenity: (amenityId) => {
    const amenity = get().amenities.find((a) => a.id === amenityId);
    set((s) => ({ amenities: s.amenities.filter((a) => a.id !== amenityId) }));
    if (amenity) {
      get().showToast(`Amenity "${amenity.name}" deleted successfully`, 'info');
      get().addActivity(`Admin deleted amenity: "${amenity.name}"`, 'general');
    }
  },

  editAmenity: (amenityId, updatedData) => {
    set((s) => ({
      amenities: s.amenities.map((a) => (a.id === amenityId ? { ...a, ...updatedData } : a)),
    }));
    get().showToast(`Amenity "${updatedData.name}" updated successfully`, 'success');
    get().addActivity(`Admin updated amenity: "${updatedData.name}"`, 'general');
  },

  toggleAmenityHold: (amenityId) => {
    const a = get().amenities.find((x) => x.id === amenityId);
    if (!a) return;
    const newStatus = a.status === 'Under Maintenance' ? 'Available' : 'Under Maintenance';
    set((s) => ({
      amenities: s.amenities.map((x) => (x.id === amenityId ? { ...x, status: newStatus } : x)),
    }));
    get().showToast(
      `Amenity "${a.name}" is now ${newStatus === 'Under Maintenance' ? 'on hold' : 'available'}`,
      'info'
    );
    get().addActivity(`Admin toggled status of "${a.name}" to ${newStatus}`, 'general');
  },
});
