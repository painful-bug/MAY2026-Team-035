import { create } from 'zustand';
import {
  createAmenity,
  getAmenityById,
  getAmenities,
  removeAmenity,
  setAmenityActiveStatus,
  updateAmenity as updateAmenityRecord,
  updateAmenitySettings as updateAmenitySettingsRecord,
} from '../services/amenitiesService.js';
import { useAppStore } from '../../../store/appStore.js';

const getErrorMessage = (error) =>
  error instanceof Error ? error.message : 'Something went wrong.';

const replaceAmenity = (amenities, updatedAmenity) =>
  amenities.map((amenity) =>
    amenity.id === updatedAmenity.id ? updatedAmenity : amenity
  );

export const useAmenitiesStore = create((set) => ({
  amenities: [],
  isLoading: false,
  isAdding: false,
  error: null,
  addError: null,
  selectedAmenity: null,
  detailAmenityId: null,
  isDetailLoading: false,
  detailError: null,
  isSavingSettings: false,
  settingsError: null,

  clearAddError: () => set({ addError: null }),
  clearSettingsError: () => set({ settingsError: null }),

  fetchAmenities: async () => {
    set({ isLoading: true, error: null });

    try {
      const amenities = await getAmenities();
      set({ amenities, isLoading: false });
      return amenities;
    } catch (error) {
      set({ error: getErrorMessage(error), isLoading: false });
      return [];
    }
  },

  fetchAmenityById: async (amenityId) => {
    set({
      detailAmenityId: amenityId,
      selectedAmenity: null,
      isDetailLoading: true,
      detailError: null,
    });

    try {
      const amenity = await getAmenityById(amenityId);
      set((state) =>
        state.detailAmenityId === amenityId
          ? { selectedAmenity: amenity, isDetailLoading: false }
          : state
      );
      return amenity;
    } catch (error) {
      set((state) =>
        state.detailAmenityId === amenityId
          ? {
              selectedAmenity: null,
              isDetailLoading: false,
              detailError: getErrorMessage(error),
            }
          : state
      );
      return null;
    }
  },

  addAmenity: async (amenityData) => {
    set({ isAdding: true, addError: null });

    try {
      const createdAmenity = await createAmenity(amenityData);
      set((state) => ({
        amenities: [...state.amenities, createdAmenity],
        isAdding: false,
      }));
      const appStore = useAppStore.getState();
      appStore.showToast(
        `Amenity "${createdAmenity.name}" added successfully`,
        'success'
      );
      appStore.addActivity(
        `Admin added amenity: "${createdAmenity.name}"`,
        'general'
      );
      return createdAmenity;
    } catch (error) {
      set({ addError: getErrorMessage(error), isAdding: false });
      return null;
    }
  },

  updateAmenity: async (amenityId, amenityData) => {
    set({ error: null });

    try {
      const amenity = await updateAmenityRecord(amenityId, amenityData);
      set((state) => ({
        amenities: replaceAmenity(state.amenities, amenity),
        selectedAmenity:
          state.detailAmenityId === amenityId
            ? amenity
            : state.selectedAmenity,
      }));
      return amenity;
    } catch (error) {
      set({ error: getErrorMessage(error) });
      return null;
    }
  },

  deleteAmenity: async (amenityId) => {
    set({ error: null });

    try {
      await removeAmenity(amenityId);
      set((state) => ({
        amenities: state.amenities.filter(
          (amenity) => amenity.id !== amenityId
        ),
        selectedAmenity:
          state.detailAmenityId === amenityId
            ? null
            : state.selectedAmenity,
      }));
      return amenityId;
    } catch (error) {
      set({ error: getErrorMessage(error) });
      return null;
    }
  },

  toggleAmenityStatus: async (amenityId) => {
    set({ error: null });

    try {
      const amenity = await setAmenityActiveStatus(amenityId);
      set((state) => ({
        amenities: replaceAmenity(state.amenities, amenity),
        selectedAmenity:
          state.detailAmenityId === amenityId
            ? amenity
            : state.selectedAmenity,
      }));
      return amenity;
    } catch (error) {
      set({ error: getErrorMessage(error) });
      return null;
    }
  },

  saveAmenitySettings: async (amenityId, settings) => {
    set({ isSavingSettings: true, settingsError: null });

    try {
      const amenity = await updateAmenitySettingsRecord(amenityId, settings);
      set((state) => ({
        amenities: replaceAmenity(state.amenities, amenity),
        selectedAmenity:
          state.detailAmenityId === amenityId
            ? amenity
            : state.selectedAmenity,
        isSavingSettings: false,
      }));
      const appStore = useAppStore.getState();
      appStore.showToast('Amenity settings saved', 'success');
      appStore.addActivity(
        `Admin updated settings for "${amenity.name}"`,
        'general'
      );
      return amenity;
    } catch (error) {
      set({
        isSavingSettings: false,
        settingsError: getErrorMessage(error),
      });
      return null;
    }
  },
}));
