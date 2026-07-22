import { create } from 'zustand';
import { DEFAULT_REPORT_FILTERS } from '../constants/amenityReports.js';
import {
  calculateAmenityReports,
  loadAmenityReportsSource,
} from '../services/amenityReportsService.js';

const EMPTY_REPORT = {
  rows: [],
  kpis: {
    totalAmenities: 0,
    totalActiveBookings: 0,
    pendingApprovals: 0,
    totalRevenue: 0,
    activeAmenities: 0,
    bookingsThisMonth: 0,
  },
  options: { amenities: [], bookingStatuses: [] },
};

const getErrorMessage = (error) =>
  error instanceof Error ? error.message : 'Unable to load amenity reports.';

export const useAmenityReportsStore = create((set, get) => ({
  source: null,
  report: EMPTY_REPORT,
  filters: { ...DEFAULT_REPORT_FILTERS },
  isLoading: false,
  error: null,

  fetchReports: async () => {
    set({ isLoading: true, error: null });
    try {
      const source = await loadAmenityReportsSource();
      const report = calculateAmenityReports(source, get().filters);
      set({ source, report, isLoading: false });
      return report;
    } catch (error) {
      set({ error: getErrorMessage(error), isLoading: false });
      return null;
    }
  },

  setFilter: (field, value) =>
    set((state) => {
      const filters = { ...state.filters, [field]: value };
      return {
        filters,
        report: state.source
          ? calculateAmenityReports(state.source, filters)
          : state.report,
      };
    }),

  resetFilters: () =>
    set((state) => ({
      filters: { ...DEFAULT_REPORT_FILTERS },
      report: state.source
        ? calculateAmenityReports(state.source, DEFAULT_REPORT_FILTERS)
        : state.report,
    })),
}));
