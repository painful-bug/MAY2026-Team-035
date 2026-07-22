import { BOOKING_STATUS } from '../constants/bookingStatuses.js';
import {
  DEFAULT_REPORT_FILTERS,
  REPORT_ALL_FILTER,
} from '../constants/amenityReports.js';
import { getAmenities } from './amenitiesService.js';
import {
  getAllAmenityBookings,
  getBookableResidents,
} from './amenityBookingsService.js';
import { getAllAmenityLedgerTransactions } from './amenityLedgerService.js';

const ACTIVE_BOOKING_STATUSES = new Set([
  BOOKING_STATUS.APPROVED,
  BOOKING_STATUS.CONFIRMED,
]);

const createActivityRow = ({ booking, transaction, amenity, resident }) => ({
  id: transaction?.id ?? `report-${booking?.id}`,
  bookingId: transaction?.bookingId ?? booking?.id,
  amenityId: transaction?.amenityId ?? booking?.amenityId,
  amenityName: amenity?.name ?? 'Unknown Amenity',
  residentName:
    transaction?.residentName ?? booking?.residentName ?? 'Administration',
  residentFlat:
    transaction?.residentFlat ?? booking?.residentFlat ?? resident?.flat ?? null,
  bookingDate: transaction?.bookingDate ?? booking?.date,
  bookingStatus: transaction?.bookingStatus ?? booking?.status,
  paymentStatus: transaction?.paymentStatus ?? null,
  amountPaid: Number(transaction?.amountPaid ?? 0),
});

const createReportsSource = ({
  amenities,
  bookings,
  transactions,
  residents,
}) => {
  const amenityById = new Map(amenities.map((amenity) => [amenity.id, amenity]));
  const residentById = new Map(
    residents.map((resident) => [resident.id, resident])
  );
  const bookingById = new Map(bookings.map((booking) => [booking.id, booking]));
  const transactionBookingIds = new Set(
    transactions.map((transaction) => transaction.bookingId)
  );
  const transactionRows = transactions.map((transaction) => {
    const booking = bookingById.get(transaction.bookingId);
    return createActivityRow({
      booking,
      transaction,
      amenity: amenityById.get(transaction.amenityId),
      resident: residentById.get(transaction.residentId),
    });
  });
  const bookingRows = bookings
    .filter((booking) => !transactionBookingIds.has(booking.id))
    .map((booking) =>
      createActivityRow({
        booking,
        amenity: amenityById.get(booking.amenityId),
        resident: residentById.get(booking.residentId),
      })
    );

  return {
    amenities: amenities.map((amenity) => ({ ...amenity })),
    rows: [...transactionRows, ...bookingRows].sort((first, second) =>
      second.bookingDate.localeCompare(first.bookingDate)
    ),
  };
};

const filterRows = (rows, filters) =>
  rows.filter((row) => {
    if (filters.startDate && row.bookingDate < filters.startDate) {
      return false;
    }
    if (filters.endDate && row.bookingDate > filters.endDate) {
      return false;
    }
    if (
      filters.amenityId !== REPORT_ALL_FILTER &&
      row.amenityId !== filters.amenityId
    ) {
      return false;
    }
    return !(
      filters.bookingStatus !== REPORT_ALL_FILTER &&
      row.bookingStatus !== filters.bookingStatus
    );
  });

export const loadAmenityReportsSource = async () => {
  const [amenities, bookings, transactions, residents] = await Promise.all([
    getAmenities(),
    getAllAmenityBookings(),
    getAllAmenityLedgerTransactions(),
    getBookableResidents(),
  ]);
  return createReportsSource({ amenities, bookings, transactions, residents });
};

export const calculateAmenityReports = (source, reportFilters) => {
  const filters = { ...DEFAULT_REPORT_FILTERS, ...reportFilters };
  const rows = filterRows(source.rows, filters);
  const representedAmenityIds = new Set(rows.map((row) => row.amenityId));
  const hasBookingFilters =
    Boolean(filters.startDate || filters.endDate) ||
    filters.bookingStatus !== REPORT_ALL_FILTER;
  const scopedAmenities =
    filters.amenityId !== REPORT_ALL_FILTER
      ? source.amenities.filter(
          (amenity) => amenity.id === filters.amenityId
        )
      : hasBookingFilters
        ? source.amenities.filter((amenity) =>
            representedAmenityIds.has(amenity.id)
          )
        : source.amenities;
  const bookingRows = rows.filter(
    (row) => row.bookingStatus !== BOOKING_STATUS.BLOCKED
  );
  const currentMonth = new Date().toISOString().slice(0, 7);

  return {
    rows,
    kpis: {
      totalAmenities: scopedAmenities.length,
      totalActiveBookings: bookingRows.filter((row) =>
        ACTIVE_BOOKING_STATUSES.has(row.bookingStatus)
      ).length,
      pendingApprovals: bookingRows.filter(
        (row) => row.bookingStatus === BOOKING_STATUS.PENDING
      ).length,
      totalRevenue: rows.reduce((total, row) => total + row.amountPaid, 0),
      activeAmenities: scopedAmenities.filter((amenity) => amenity.isActive)
        .length,
      bookingsThisMonth: bookingRows.filter((row) =>
        row.bookingDate.startsWith(currentMonth)
      ).length,
    },
    options: {
      amenities: source.amenities.map(({ id, name }) => ({
        value: id,
        label: name,
      })),
      bookingStatuses: [
        ...new Set(source.rows.map((row) => row.bookingStatus).filter(Boolean)),
      ],
    },
  };
};
