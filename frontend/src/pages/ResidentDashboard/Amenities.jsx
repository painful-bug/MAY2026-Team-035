import React, {
  useCallback,
  useEffect,
  useMemo,
  useState,
} from 'react';
import { createPortal } from 'react-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  AlertCircle,
  CalendarDays,
  CalendarRange,
  CheckCircle,
  Clock,
  MapPin,
  Plus,
  Trash2,
  Users,
  X,
} from 'lucide-react';
import { BOOKING_MODE } from '../../features/amenities/constants/bookingModes.js';
import {
  bookingStatusLabel,
  normalizeBookingStatus,
} from '../../features/amenities/constants/bookingStatuses.js';
import {
  cancelResidentAmenityBookingDays,
  createResidentAmenityBookingSeries,
  evaluateBookingSlot,
  fetchBookingConflicts,
} from '../../features/amenities/services/amenityBookingsService.js';
import { DEFAULT_AMENITY_SETTINGS } from '../../features/amenities/constants/amenitySettings.js';
import { normalizeAmenityRecord } from '../../features/amenities/utils/amenitySettingsModel.js';
import {
  createBookingSlots,
  formatTime,
  hasBookableHours,
} from '../../features/amenities/utils/bookingSlots.js';
import { residentApi } from '../../features/resident/residentApi.js';
import { useAppStore } from '../../store/appStore.js';
import { useAuthStore } from '../../store/authStore.js';

// The catalogue below is wired to `GET /amenities/available`
// (`docs/API.md` §10, `backend/app/api/v1/routers/resident_amenities.py`) —
// this is finding 3.1's fix: the old `useAmenitiesStore` read
// `getDashboardSnapshot()`, i.e. `GET /dashboard/snapshot`, which is
// ADMIN/MANAGER-guarded and 403s a resident. `BookableAmenity` is a distinct,
// narrower projection (no `pendingRequests`/`outstandingDues`), so it is
// mapped onto the shape the existing booking UI already expects rather than
// the admin shape it used to read.
//
// **Booking creation stays exactly as it was.** It already calls real
// endpoints (`POST /amenities/{id}/bookings/request`,
// `POST /amenity-bookings/cancel`) — that part of the demo was not invented.
//
// **"Your Bookings" now reads `GET /amenity-bookings/mine`.** It used to call
// `getResidentAmenityBookings`, which filtered `GET /dashboard/snapshot` by the
// caller's id — and that endpoint is ADMIN/MANAGER-guarded, so the table this
// page opens with `403`d for every resident who has ever looked at it. The
// replacement is scoped by the server to the caller's own membership, so there
// is no resident id to pass and nothing to filter client-side.
//
// The two shapes are not the same, which is why `mapResidentBooking` exists:
// `ResidentBooking` carries an instant (`startsAt`/`endsAt`) rather than the
// wall-clock `HH:MM` pair the demo stored, groups by `bookingSeriesId` rather
// than `bookingGroupId`, and speaks the database's status vocabulary
// (`requested`, not `pending`) beside a display string of its own.
const mapBookableAmenity = (item) =>
  normalizeAmenityRecord({
    id: item.id,
    name: item.name,
    description: item.description,
    category: item.category,
    location: item.location,
    image: item.image,
    capacity: item.capacity,
    isActive: true,
    status: 'Active',
    operatingHours: {
      openingTime: item.openingTime,
      closingTime: item.closingTime,
      slotDurationMinutes: item.slotDurationMinutes,
      cleaningBufferMinutes: 0,
    },
    bookingSettings: {
      mode: item.bookingMode,
      maxActiveBookingsPerResident: item.maxActiveBookingsPerResident,
      requireAdminApproval: item.requiresApproval,
      allowPrivateBooking: item.allowPrivateBooking,
      allowRecurringBooking: item.allowRecurringBooking,
      allowGuestBooking: item.allowGuestBooking,
      allowSameDayBooking: item.allowSameDayBooking,
      enableWaitlist: false,
      enableAutoApproval: false,
    },
    paymentSettings: {
      bookingFee: item.bookingFee,
      securityDeposit: item.securityDeposit,
      lateCancellationCharge: 0,
      damageDeposit: 0,
      refundPolicy: item.refundPolicy,
      currency: item.currencyCode,
    },
    availabilitySettings: {
      // `closedDays` is real; `maintenanceDays` / `holidayOverrides` have no
      // resident-facing reader (admin-only fields), so they are empty rather
      // than guessed at.
      closedDays: item.closedDays || [],
      maintenanceDays: [],
      holidayOverrides: [],
      temporaryClosure: false,
      // `null` on the wire means "this amenity sets no limit of its own", not
      // "there is no limit" (docs/API.md §10) — the booking RPC still applies
      // its own rules on write. The client-side slot math needs a concrete
      // number, so a `null` here falls back to the same defaults the admin
      // settings form ships with, not to an invented value.
      minimumBookingDurationMinutes:
        item.minimumBookingDurationMinutes ??
        DEFAULT_AMENITY_SETTINGS.availabilitySettings.minimumBookingDurationMinutes,
      maximumBookingDurationMinutes:
        item.maximumBookingDurationMinutes ??
        DEFAULT_AMENITY_SETTINGS.availabilitySettings.maximumBookingDurationMinutes,
      advanceBookingWindowDays:
        item.advanceBookingWindowDays ??
        DEFAULT_AMENITY_SETTINGS.availabilitySettings.advanceBookingWindowDays,
    },
  });

// `GET /amenity-bookings/mine` → the shape the bookings table already speaks.
//
// Three translations, each of them a real difference rather than a rename:
//
//   status — the wire carries the DATABASE's vocabulary
//     (`requested | approved | rejected | cancelled | completed | no_show`),
//     and the frontend's constant calls the first of those `pending`. Only
//     that one word differs, so only that one is mapped. The DISPLAY wording
//     is no longer taken from the response: the server used to send a
//     Title-case string beside the stored one and it is a machine value now
//     (issue #48, contract §C), so `bookingStatusLabel` — which knows about
//     `no_show` — decides the casing here.
//
//   dates — `bookingDate` is already the calendar day in the COMMUNITY's
//     timezone, computed in the view. `startsAt`/`endsAt` are instants, and the
//     community's timezone is not in the response, so the clock times are
//     rendered in the reader's own zone. For this product those are the same
//     zone; when they are not, the resident's own is the right one to show.
//
//   cancellability — the demo asked `source === 'resident'`, a field that does
//     not exist here. `isUpcoming` is the database's answer to the same
//     question the cancel RPC enforces (`starts_at >= now()`), so the button is
//     offered on exactly the days the write will accept.
const mapResidentBookingStatus = (item) => {
  const stored = normalizeBookingStatus(item.storedStatus ?? item.status);
  return stored === 'requested' ? 'pending' : stored;
};

const mapResidentBooking = (item) => {
  const status = mapResidentBookingStatus(item);

  return {
    id: item.id,
    bookingGroupId: item.bookingSeriesId,
    amenityId: item.amenityId,
    amenityName: item.amenityName,
    date: item.bookingDate ?? String(item.startsAt).slice(0, 10),
    startsAt: item.startsAt,
    endsAt: item.endsAt,
    status,
    statusLabel: bookingStatusLabel(status),
    isUpcoming: Boolean(item.isUpcoming),
  };
};

// `confirmed` was in this list and is not a status any endpoint can send: the
// lifecycle is {pending, approved, rejected, cancelled, completed, no_show}
// (issue #48, contract §C — an admin-created booking is `approved`, and a block
// is an approved row with `bookingType: 'blocked'`). A day is withdrawable
// while it is still waiting or already granted.
const CANCELLABLE_STATUSES = ['pending', 'approved'];

const isCancellableDay = (booking) =>
  booking.isUpcoming && CANCELLABLE_STATUSES.includes(booking.status);

const todayISO = () => new Date().toISOString().split('T')[0];

const getDatesInRange = (startDate, endDate) => {
  if (!startDate || !endDate || endDate < startDate) return [];

  const dates = [];
  const current = new Date(`${startDate}T00:00:00.000Z`);
  const end = new Date(`${endDate}T00:00:00.000Z`);
  while (current <= end) {
    dates.push(current.toISOString().split('T')[0]);
    current.setUTCDate(current.getUTCDate() + 1);
  }
  return dates;
};

const formatBookingDate = (date) =>
  new Intl.DateTimeFormat('en-IN', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    timeZone: 'UTC',
  }).format(new Date(`${date}T00:00:00.000Z`));

const groupResidentBookings = (bookings) => {
  const groups = new Map();
  bookings.forEach((booking) => {
    const groupId = booking.bookingGroupId ?? booking.id;
    const currentGroup = groups.get(groupId) ?? [];
    currentGroup.push(booking);
    groups.set(groupId, currentGroup);
  });

  return [...groups.entries()]
    .map(([id, records]) => ({
      id,
      records: records.sort((first, second) =>
        first.date.localeCompare(second.date)
      ),
    }))
    .sort((first, second) =>
      first.records[0].date.localeCompare(second.records[0].date)
    );
};

const getGroupStatus = (records) => {
  const statuses = new Set(records.map((record) => record.status));
  const hasCancelled = statuses.has('cancelled');
  const hasActive = records.some((record) =>
    CANCELLABLE_STATUSES.includes(record.status)
  );

  if (hasCancelled && hasActive) {
    return {
      key: 'partially-cancelled',
      label: 'Partially Cancelled',
    };
  }

  if (statuses.size === 1) {
    const [record] = records;
    return {
      key: record.status,
      label: record.statusLabel ?? bookingStatusLabel(record.status),
    };
  }

  return { key: 'mixed', label: 'Mixed Status' };
};

// `timeToMinutes` / `minutesToTime` / `formatTime` / `createBookingSlots`
// moved to `features/amenities/utils/bookingSlots.js` (with the new
// `hasBookableHours`) so the empty-hours behaviour has unit tests.

// For `startsAt` / `endsAt`, which are instants rather than the wall-clock
// `HH:MM` strings above. No `timeZone`: the response does not carry the
// community's, and the reader's own is the one a resident recognises.
const formatInstantTime = (timestamp) => {
  const value = new Date(timestamp);
  return Number.isNaN(value.getTime())
    ? '—'
    : new Intl.DateTimeFormat('en-IN', {
        hour: 'numeric',
        minute: '2-digit',
        hour12: true,
      }).format(value);
};

const getClosureReason = (amenity, date) => {
  if (!amenity?.isActive) {
    return 'This amenity has been disabled by the administrator.';
  }

  if (!date) {
    return 'Select a booking date.';
  }

  const availability = amenity.availabilitySettings;

  if (availability.temporaryClosure) {
    return 'This amenity is temporarily closed.';
  }

  const dayName = new Intl.DateTimeFormat('en-US', {
    weekday: 'long',
    timeZone: 'UTC',
  }).format(new Date(`${date}T00:00:00.000Z`));

  if (availability.closedDays.includes(dayName)) {
    return `This amenity is closed on ${dayName}s.`;
  }

  if (availability.maintenanceDays.includes(dayName)) {
    return `This amenity is under maintenance on ${dayName}s.`;
  }

  if (availability.holidayOverrides.includes(date)) {
    return 'This amenity is closed on the selected date.';
  }

  return '';
};

const statusClassNames = {
  pending: 'border-amber-100 bg-amber-50 text-amber-700',
  approved: 'border-emerald-100 bg-emerald-50 text-emerald-700',
  confirmed: 'border-emerald-100 bg-emerald-50 text-emerald-700',
  rejected: 'border-rose-100 bg-rose-50 text-rose-700',
  cancelled: 'border-slate-200 bg-slate-50 text-slate-600',
  'partially-cancelled': 'border-amber-100 bg-amber-50 text-amber-700',
  mixed: 'border-indigo-100 bg-indigo-50 text-indigo-700',
};

export default function Amenities() {
  const queryClient = useQueryClient();
  const amenitiesQuery = useQuery({
    queryKey: ['resident', 'amenities-available'],
    queryFn: () => residentApi.availableAmenities(),
  });
  const amenities = useMemo(
    () => (amenitiesQuery.data?.items || []).map(mapBookableAmenity),
    [amenitiesQuery.data]
  );
  const isLoading = amenitiesQuery.isLoading;
  const amenitiesError = amenitiesQuery.error
    ? amenitiesQuery.error.message || 'Could not load amenities.'
    : null;
  const fetchAmenities = useCallback(
    () => queryClient.invalidateQueries({ queryKey: ['resident', 'amenities-available'] }),
    [queryClient]
  );
  const currentUser = useAuthStore((state) => state.currentUser);
  const searchQuery = useAppStore((state) => state.searchQuery);
  const showToast = useAppStore((state) => state.showToast);
  const addActivity = useAppStore((state) => state.addActivity);
  const [amenityId, setAmenityId] = useState('');
  const [date, setDate] = useState(todayISO);
  const [endDate, setEndDate] = useState(todayISO);
  const [timeSlot, setTimeSlot] = useState('');
  const [guestCount, setGuestCount] = useState(0);
  const [isPrivateBooking, setIsPrivateBooking] = useState(false);
  const [availableSlotValues, setAvailableSlotValues] = useState(new Set());
  // `isCheckingSlots` itself is now derived from the conflicts query below
  // rather than its own state (see `bookingConflictsQuery`).
  // Whether the last slot check actually reached the conflict data. False
  // means the slots on offer are unfiltered rather than known-free.
  const [isAvailabilityVerified, setIsAvailabilityVerified] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState('');
  const [bookingRevision, setBookingRevision] = useState(0);
  const [isBookingModalOpen, setIsBookingModalOpen] = useState(false);
  const [managedBookingGroupId, setManagedBookingGroupId] = useState(null);
  const [selectedCancellationIds, setSelectedCancellationIds] = useState([]);
  const [cancellationReason, setCancellationReason] = useState('');
  const [cancellationError, setCancellationError] = useState('');
  const [isCancelling, setIsCancelling] = useState(false);

  // The caller's own bookings. No resident id anywhere in this call: the server
  // scopes it to the authenticated membership, which is the whole reason it
  // replaced the admin snapshot read.
  const bookingsQuery = useQuery({
    queryKey: ['resident', 'amenity-bookings'],
    queryFn: () => residentApi.amenityBookings({ pageSize: 100 }),
  });
  const userBookings = useMemo(
    () => (bookingsQuery.data?.items || []).map(mapResidentBooking),
    [bookingsQuery.data]
  );
  const loadUserBookings = useCallback(
    () =>
      queryClient.invalidateQueries({
        queryKey: ['resident', 'amenity-bookings'],
      }),
    [queryClient]
  );

  // There used to be a `homebandhu:dashboard-refresh` listener here, re-reading
  // the amenities, the bookings and the conflict snapshot. That window event is
  // dispatched by `DashboardDataBootstrap`, which mounts in `AdminLayout` and
  // nowhere else — so on the resident portal it never fired, and this screen
  // has never once updated itself while somebody else took the 6pm slot.
  //
  // `ResidentLayout` now subscribes to the real stream for the whole portal,
  // and `amenity.changed` (audience: community) stales exactly those three
  // reads — see `RESIDENT_EVENT_MAP` in `features/resident/residentEvents.js`.
  // Both `useQuery` calls above still fetch on mount, so there is no initial
  // fetch to replace.

  useEffect(() => {
    if (
      amenities.length > 0 &&
      !amenities.some((amenity) => amenity.id === amenityId)
    ) {
      const firstAvailableAmenity =
        amenities.find((amenity) => amenity.isActive) ?? amenities[0];
      setAmenityId(firstAvailableAmenity.id);
    }
  }, [amenities, amenityId]);

  const selectedAmenity = amenities.find(
    (amenity) => amenity.id === amenityId
  );
  const bookingSlots = useMemo(
    () => createBookingSlots(selectedAmenity),
    [selectedAmenity]
  );
  // "00:00"/"00:00" is how the API spells hours that were never set (NULL in
  // the amenities row). The slot builder correctly yields nothing for it, but
  // an empty disabled dropdown explains nothing — the dialog says so instead.
  const amenityHasBookableHours = hasBookableHours(selectedAmenity);
  const bookingDates = useMemo(
    () => getDatesInRange(date, endDate),
    [date, endDate]
  );
  const closureReason = selectedAmenity
    ? bookingDates
        .map((bookingDate) => ({
          date: bookingDate,
          reason: getClosureReason(selectedAmenity, bookingDate),
        }))
        .filter((item) => item.reason)
        .map((item) => `${formatBookingDate(item.date)}: ${item.reason}`)[0] ??
      (bookingDates.length === 0 ? 'Select a valid date range.' : '')
    : '';

  // The slot hint. It is allowed to fail — the conflict read is the
  // ADMIN-guarded snapshot and answers `verified: false` for the resident it
  // 403s — and it is not allowed to hang: an unhandled rejection here used to
  // leave `isCheckingSlots` true for good, so the dropdown said "Checking
  // availability..." until the page was reloaded, with the submit button
  // disabled behind it. Every exit path clears the flag, and an unverified
  // check offers every slot rather than claiming an availability nobody
  // looked up. The booking write is the authority either way: a taken slot
  // comes back as a `409` with a message the form already renders.
  //
  // ONE fetch per amenity/date-range/revision change, not one per slot-date
  // pair: `fetchBookingConflicts` pulls the snapshot once and every slot-date
  // question is answered locally from it by `evaluateBookingSlot` below.
  // `guestCount` and `isPrivateBooking` deliberately do not re-trigger the
  // fetch — they change which slots the same bookings admit, which is pure
  // local arithmetic recomputed in the memo underneath.
  //
  // On React Query rather than its own `useEffect` + `ignore` flag: the query
  // key below carries the exact same dependency set the old effect ran on
  // (amenity, date range, closure, slots, revision), so this fires on the
  // same occasions the effect did — React Query's own key-based dedup
  // replaces the manual `ignore` guard against a stale response landing after
  // a newer one. `staleTime: 0` is deliberate: this is a live availability
  // check, not cacheable reference data, so every dependency change (or
  // remount) is trusted to ask the server again rather than reuse a cached
  // answer.
  const shouldCheckSlots =
    Boolean(selectedAmenity) && !closureReason && bookingSlots.length > 0;
  const bookingConflictsQuery = useQuery({
    queryKey: [
      'resident',
      'amenity-booking-conflicts',
      selectedAmenity?.id,
      bookingDates,
      closureReason,
      bookingSlots.map((slot) => slot.value),
      bookingRevision,
    ],
    // `fetchBookingConflicts` already resolves `verified: false` rather than
    // rejecting when the snapshot is refused; the catch is belt-and-braces so
    // a surprise rejection can never strand `isCheckingSlots` again.
    queryFn: () =>
      fetchBookingConflicts().catch(() => ({ bookings: [], verified: false })),
    enabled: shouldCheckSlots,
    staleTime: 0,
    gcTime: 5 * 60_000,
  });
  const bookingConflicts = shouldCheckSlots
    ? bookingConflictsQuery.data ?? null
    : null;
  const isCheckingSlots = shouldCheckSlots && bookingConflictsQuery.isFetching;

  // Which slots the fetched conflicts admit, recomputed locally on every
  // guest-count or private-booking keystroke without touching the network.
  const slotAvailability = useMemo(() => {
    if (!selectedAmenity || closureReason || bookingSlots.length === 0) {
      return { ready: false, values: new Set(), verified: true };
    }
    if (!bookingConflicts) {
      return { ready: false, values: new Set(), verified: true };
    }

    try {
      const values = new Set(
        bookingSlots
          .filter((slot) =>
            bookingDates.every((bookingDate) =>
              evaluateBookingSlot({
                amenityId: selectedAmenity.id,
                date: bookingDate,
                startTime: slot.startTime,
                endTime: slot.endTime,
                openingTime: selectedAmenity.openingTime,
                closingTime: selectedAmenity.closingTime,
                cleaningBuffer: selectedAmenity.cleaningBuffer,
                bookingMode: selectedAmenity.bookingMode,
                isPrivateBooking,
                guestCount,
                capacity: selectedAmenity.capacity,
                bookings: bookingConflicts.bookings,
              })
            )
          )
          .map((slot) => slot.value)
      );
      return { ready: true, values, verified: bookingConflicts.verified };
    } catch {
      // Nothing is known about conflicts, so nothing is greyed out: the
      // resident picks a slot and the write decides.
      return {
        ready: true,
        values: new Set(bookingSlots.map((slot) => slot.value)),
        verified: false,
      };
    }
  }, [
    selectedAmenity,
    closureReason,
    bookingSlots,
    bookingDates,
    bookingConflicts,
    isPrivateBooking,
    guestCount,
  ]);

  useEffect(() => {
    if (!slotAvailability.ready) {
      setTimeSlot('');
      setAvailableSlotValues(new Set());
      return;
    }

    setAvailableSlotValues(slotAvailability.values);
    setTimeSlot(
      bookingSlots.find((slot) => slotAvailability.values.has(slot.value))
        ?.value ?? ''
    );
    setIsAvailabilityVerified(slotAvailability.verified);
  }, [slotAvailability, bookingSlots]);

  useEffect(() => {
    const supportsPrivateBooking =
      selectedAmenity?.bookingMode === BOOKING_MODE.EXCLUSIVE ||
      (selectedAmenity?.bookingMode === BOOKING_MODE.HYBRID &&
        selectedAmenity?.bookingSettings.allowPrivateBooking);

    if (!supportsPrivateBooking) {
      setIsPrivateBooking(false);
    }

    if (!selectedAmenity?.bookingSettings.allowGuestBooking) {
      setGuestCount(0);
    }
  }, [selectedAmenity]);

  useEffect(() => {
    if (!isBookingModalOpen && !managedBookingGroupId) {
      return undefined;
    }

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const handleEscape = (event) => {
      if (event.key === 'Escape' && !isSubmitting) {
        setIsBookingModalOpen(false);
        setManagedBookingGroupId(null);
      }
    };

    document.addEventListener('keydown', handleEscape);
    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener('keydown', handleEscape);
    };
  }, [
    isBookingModalOpen,
    managedBookingGroupId,
    isSubmitting,
  ]);

  const filteredAmenitiesCatalog = amenities.filter((amenity) => {
    const normalizedSearch = (searchQuery || '').trim().toLowerCase();
    return (
      !normalizedSearch ||
      amenity.name.toLowerCase().includes(normalizedSearch) ||
      amenity.description.toLowerCase().includes(normalizedSearch) ||
      amenity.category.toLowerCase().includes(normalizedSearch)
    );
  });

  const handleSubmit = async (event) => {
    event.preventDefault();
    setFormError('');

    const slot = bookingSlots.find((item) => item.value === timeSlot);

    if (!selectedAmenity || !slot || closureReason) {
      setFormError(closureReason || 'Select an available time slot.');
      return;
    }

    setIsSubmitting(true);
    const bookingData = {
      amenityId: selectedAmenity.id,
      residentId: currentUser.id,
      residentName: currentUser.name,
      bookingTitle: isPrivateBooking
        ? 'Private Resident Booking'
        : 'Resident Booking',
      bookingType: isPrivateBooking ? 'private-event' : 'resident',
      date: bookingDates[0],
      dates: bookingDates,
      startTime: slot.startTime,
      endTime: slot.endTime,
      isPrivateBooking,
      guestCount,
      notes: '',
    };

    try {
      const createdBookings =
        await createResidentAmenityBookingSeries(bookingData);
      await loadUserBookings();
      setBookingRevision((revision) => revision + 1);
      const message =
        createdBookings[0].status === 'pending'
          ? `${createdBookings.length}-day booking request sent for admin approval`
          : `${selectedAmenity.name} booked for ${createdBookings.length} day${createdBookings.length === 1 ? '' : 's'}`;
      showToast(message, 'success');
      addActivity(
        `You booked ${selectedAmenity.name} from ${bookingDates[0]} to ${bookingDates[bookingDates.length - 1]}`,
        'general'
      );
      setIsBookingModalOpen(false);
    } catch (error) {
      setFormError(
        error instanceof Error ? error.message : 'Unable to create booking.'
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  const openBookingModal = (amenity) => {
    setAmenityId(amenity.id);
    setDate(todayISO());
    setEndDate(todayISO());
    setGuestCount(0);
    setIsPrivateBooking(amenity.bookingMode === BOOKING_MODE.EXCLUSIVE);
    setFormError('');
    setIsBookingModalOpen(true);
  };

  const closeBookingModal = () => {
    if (!isSubmitting) {
      setIsBookingModalOpen(false);
      setFormError('');
    }
  };

  const maximumDate = useMemo(() => {
    const result = new Date(`${todayISO()}T00:00:00.000Z`);
    result.setUTCDate(
      result.getUTCDate() +
        (selectedAmenity?.availabilitySettings.advanceBookingWindowDays ?? 30)
    );
    return result.toISOString().split('T')[0];
  }, [selectedAmenity]);

  const supportsSharedBooking =
    selectedAmenity?.bookingMode !== BOOKING_MODE.EXCLUSIVE;
  const supportsPrivateBooking =
    selectedAmenity?.bookingMode === BOOKING_MODE.EXCLUSIVE ||
    (selectedAmenity?.bookingMode === BOOKING_MODE.HYBRID &&
      selectedAmenity?.bookingSettings.allowPrivateBooking);
  const requiresAdminApproval =
    selectedAmenity?.bookingSettings.requireAdminApproval &&
    !selectedAmenity?.bookingSettings.enableAutoApproval;
  const groupedBookings = useMemo(
    () => groupResidentBookings(userBookings),
    [userBookings]
  );
  const managedBookingGroup = groupedBookings.find(
    (group) => group.id === managedBookingGroupId
  );
  const cancellableManagedBookings =
    managedBookingGroup?.records.filter(isCancellableDay) ?? [];

  const openCancellationModal = (groupId) => {
    setManagedBookingGroupId(groupId);
    setSelectedCancellationIds([]);
    setCancellationReason('');
    setCancellationError('');
  };

  const closeCancellationModal = () => {
    if (!isCancelling) {
      setManagedBookingGroupId(null);
      setCancellationError('');
    }
  };

  const handlePartialCancellation = async (event) => {
    event.preventDefault();
    setCancellationError('');
    setIsCancelling(true);

    try {
      const cancelledBookings =
        await cancelResidentAmenityBookingDays({
          // No resident id: the server decides which days this caller may
          // withdraw from the authenticated membership.
          bookingIds: selectedCancellationIds,
          reason: cancellationReason,
        });
      await loadUserBookings();
      setBookingRevision((revision) => revision + 1);
      showToast(
        `${cancelledBookings.length} booking day${cancelledBookings.length === 1 ? '' : 's'} cancelled`,
        'success'
      );
      addActivity(
        `You cancelled ${cancelledBookings.length} day${cancelledBookings.length === 1 ? '' : 's'} from an amenity booking`,
        'general'
      );
      setManagedBookingGroupId(null);
    } catch (error) {
      setCancellationError(
        error instanceof Error
          ? error.message
          : 'Unable to cancel the selected days.'
      );
    } finally {
      setIsCancelling(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-extrabold tracking-tight text-slate-900">
          Amenities Booking
        </h1>
        <p className="mt-1 text-xs font-semibold text-slate-400">
          View live facility availability and reserve a society amenity.
        </p>
      </div>

      <div className="flex flex-col overflow-hidden rounded-2xl border border-slate-100 bg-white shadow-sm">
        <div className="flex items-center justify-between border-b border-slate-50 p-6">
          <div className="flex items-center gap-2">
            <CalendarDays className="h-5 w-5 text-indigo-600" />
            <h2 className="text-sm font-extrabold text-slate-800">
              Your Bookings
            </h2>
          </div>
          <span className="rounded-lg border border-slate-100 bg-slate-50 px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider text-slate-500">
            {groupedBookings.length} Bookings
          </span>
        </div>

        <div className="overflow-x-auto">
          {bookingsQuery.isPending ? (
            <div className="py-12 text-center text-xs font-semibold text-slate-400">
              Loading your bookings...
            </div>
          ) : bookingsQuery.error ? (
            <div className="px-6 py-12 text-center">
              <p role="alert" className="text-xs font-bold text-rose-700">
                {bookingsQuery.error.message ||
                  'Could not load your bookings.'}
              </p>
              <button
                type="button"
                onClick={() => bookingsQuery.refetch()}
                className="mt-3 rounded-xl border border-rose-100 bg-white px-4 py-2 text-xs font-bold text-rose-700 hover:bg-rose-50"
              >
                Try again
              </button>
            </div>
          ) : groupedBookings.length === 0 ? (
            <div className="py-12 text-center text-xs font-semibold text-slate-400">
              You have no amenity reservations.
            </div>
          ) : (
            <table className="w-full border-collapse text-left">
              <thead>
                <tr className="border-b border-slate-100 bg-slate-50/50 text-[10px] font-extrabold uppercase tracking-wider text-slate-400">
                  <th className="px-6 py-3.5">Facility</th>
                  <th className="px-6 py-3.5">Reserved Dates</th>
                  <th className="px-6 py-3.5">Time Slot</th>
                  <th className="px-6 py-3.5">Status</th>
                  <th className="px-6 py-3.5 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-50 text-xs font-semibold text-slate-600">
                {groupedBookings.map((group) => {
                  const firstBooking = group.records[0];
                  const lastBooking =
                    group.records[group.records.length - 1];
                  const groupStatus = getGroupStatus(group.records);
                  const cancellableBookings =
                    group.records.filter(isCancellableDay);
                  return (
                    <tr
                      key={group.id}
                      className="transition-colors hover:bg-slate-50/30"
                    >
                      {/* The name travels with the booking now, so a facility
                          that has since been deactivated still reads as itself
                          rather than as "Removed amenity" — the resident's own
                          history should not be edited by an admin's toggle. */}
                      <td className="px-6 py-4 font-bold text-slate-800">
                        {firstBooking.amenityName || 'Amenity'}
                      </td>
                      <td className="px-6 py-4">
                        <span className="font-bold text-slate-700">
                          {formatBookingDate(firstBooking.date)}
                          {group.records.length > 1 &&
                            ` – ${formatBookingDate(lastBooking.date)}`}
                        </span>
                        <span className="mt-0.5 block text-[10px] text-slate-400">
                          {group.records.length} day
                          {group.records.length === 1 ? '' : 's'}
                        </span>
                      </td>
                      <td className="px-6 py-4 font-mono text-indigo-700">
                        {formatInstantTime(firstBooking.startsAt)} -{' '}
                        {formatInstantTime(firstBooking.endsAt)}
                      </td>
                      <td className="px-6 py-4">
                        <span
                          className={`flex w-fit items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-bold ${
                            statusClassNames[groupStatus.key] ??
                            'border-slate-200 bg-slate-50 text-slate-600'
                          }`}
                        >
                          <CheckCircle className="h-3 w-3" />
                          {groupStatus.label}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-right">
                        {cancellableBookings.length > 0 && (
                          <button
                            type="button"
                            onClick={() =>
                              openCancellationModal(group.id)
                            }
                            className="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-[10px] font-bold text-slate-600 transition-colors hover:border-rose-200 hover:bg-rose-50 hover:text-rose-600"
                          >
                            Manage days
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      </div>

      <div>
        <h2 className="text-base font-extrabold text-slate-800">
          Explore Amenities
        </h2>
        <p className="mt-1 text-xs font-semibold text-slate-400">
          Select an amenity to view its details and book an available slot.
        </p>
      </div>

      {isLoading && amenities.length === 0 ? (
        <div className="rounded-2xl border border-slate-100 bg-white px-6 py-12 text-center text-xs font-semibold text-slate-400">
          Loading amenities...
        </div>
      ) : amenitiesError && amenities.length === 0 ? (
        <div className="rounded-2xl border border-rose-100 bg-rose-50 px-6 py-10 text-center">
          <p className="text-xs font-bold text-rose-700">{amenitiesError}</p>
          <button
            type="button"
            onClick={fetchAmenities}
            className="mt-3 rounded-xl bg-white px-4 py-2 text-xs font-bold text-rose-700"
          >
            Try again
          </button>
        </div>
      ) : filteredAmenitiesCatalog.length === 0 ? (
        <div className="rounded-2xl border border-slate-100 bg-white px-6 py-12 text-center text-xs font-semibold text-slate-400">
          No amenities match your search.
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-3">
          {filteredAmenitiesCatalog.map((amenity) => {
            const isAvailable =
              amenity.isActive &&
              !amenity.availabilitySettings.temporaryClosure;

            return (
              <button
                type="button"
                key={amenity.id}
                onClick={() => openBookingModal(amenity)}
                className="group overflow-hidden rounded-2xl border border-slate-100 bg-white text-left shadow-sm transition-all hover:-translate-y-0.5 hover:border-indigo-200 hover:shadow-md focus:outline-none focus:ring-2 focus:ring-indigo-200"
              >
                {amenity.image && (
                  <img
                    src={amenity.image}
                    alt=""
                    className="h-32 w-full object-cover transition-transform duration-300 group-hover:scale-[1.02]"
                  />
                )}
                <div className="space-y-4 p-5">
                  <div className="space-y-2">
                    <span
                      className={`inline-block rounded-lg border px-2.5 py-1 text-[10px] font-extrabold uppercase tracking-wider ${
                        isAvailable
                          ? 'border-emerald-100 bg-emerald-50 text-emerald-700'
                          : 'border-rose-100 bg-rose-50 text-rose-700'
                      }`}
                    >
                      {isAvailable ? 'Available' : 'Unavailable'}
                    </span>
                    <h3 className="text-base font-extrabold text-slate-800">
                      {amenity.name}
                    </h3>
                    <p className="text-xs font-semibold leading-relaxed text-slate-500">
                      {amenity.description}
                    </p>
                  </div>
                  <div className="space-y-2 border-t border-slate-50 pt-3 text-xs font-bold text-slate-500">
                    {/* Only when the amenity really has hours — `openingHours`
                        is '' for the NULL-hours rows, and a clock icon beside
                        nothing is noise. */}
                    {amenity.openingHours && (
                      <div className="flex items-center gap-2">
                        <Clock className="h-4 w-4 text-indigo-500" />
                        <span>{amenity.openingHours}</span>
                      </div>
                    )}
                    <div className="flex items-center gap-2">
                      <Users className="h-4 w-4 text-indigo-500" />
                      <span>Capacity: {amenity.capacity ?? 'Not limited'}</span>
                    </div>
                    {amenity.location && (
                      <div className="flex items-center gap-2">
                        <MapPin className="h-4 w-4 text-indigo-500" />
                        <span>{amenity.location}</span>
                      </div>
                    )}
                  </div>
                  <div className="flex items-center justify-between border-t border-slate-50 pt-3">
                    <span className="text-[10px] font-extrabold uppercase tracking-wider text-indigo-600">
                      View details &amp; book
                    </span>
                    <span className="text-sm font-bold text-indigo-500 transition-transform group-hover:translate-x-0.5">
                      →
                    </span>
                  </div>
                </div>
              </button>
            );
          })}
        </div>
      )}

      {isBookingModalOpen && selectedAmenity && createPortal(
        <div
          className="fixed inset-0 z-[999] flex items-start justify-center overflow-y-auto bg-slate-900/60 p-8 backdrop-blur-sm"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) {
              closeBookingModal();
            }
          }}
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="resident-amenity-booking-title"
            className="max-h-[calc(100vh-4rem)] w-full max-w-2xl overflow-y-auto rounded-3xl border border-slate-100 bg-white shadow-xl"
          >
            {selectedAmenity.image && (
              <div className="relative h-44 overflow-hidden rounded-t-3xl">
                <img
                  src={selectedAmenity.image}
                  alt=""
                  className="h-full w-full object-cover"
                />
                <div className="absolute inset-0 bg-gradient-to-t from-slate-950/65 to-transparent" />
                <div className="absolute bottom-5 left-6 right-6 text-white">
                  <p className="text-[10px] font-bold uppercase tracking-wider text-white/75">
                    {selectedAmenity.category}
                  </p>
                  <h2
                    id="resident-amenity-booking-title"
                    className="mt-1 text-xl font-extrabold"
                  >
                    {selectedAmenity.name}
                  </h2>
                </div>
                <button
                  type="button"
                  onClick={closeBookingModal}
                  className="absolute right-4 top-4 flex h-9 w-9 items-center justify-center rounded-full bg-white/90 text-slate-700 shadow-sm transition-colors hover:bg-white"
                  aria-label="Close booking form"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            )}

            <div className="space-y-6 p-6">
              {!selectedAmenity.image && (
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <p className="text-[10px] font-bold uppercase tracking-wider text-indigo-600">
                      {selectedAmenity.category}
                    </p>
                    <h2
                      id="resident-amenity-booking-title"
                      className="mt-1 text-xl font-extrabold text-slate-900"
                    >
                      {selectedAmenity.name}
                    </h2>
                  </div>
                  <button
                    type="button"
                    onClick={closeBookingModal}
                    className="flex h-9 w-9 items-center justify-center rounded-full bg-slate-100 text-slate-600 transition-colors hover:bg-slate-200"
                    aria-label="Close booking form"
                  >
                    <X className="h-4 w-4" />
                  </button>
                </div>
              )}

              <div>
                <p className="text-xs font-semibold leading-relaxed text-slate-500">
                  {selectedAmenity.description}
                </p>
                {selectedAmenity.location && (
                  <p className="mt-2 flex items-center gap-1.5 text-xs font-bold text-slate-600">
                    <MapPin className="h-4 w-4 text-indigo-500" />
                    {selectedAmenity.location}
                  </p>
                )}
              </div>

              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                <div className="rounded-xl border border-slate-100 bg-slate-50 p-3">
                  <p className="text-[9px] font-extrabold uppercase tracking-wider text-slate-400">
                    Opening Time
                  </p>
                  <p className="mt-1 text-sm font-extrabold text-slate-700">
                    {amenityHasBookableHours
                      ? formatTime(selectedAmenity.openingTime)
                      : 'Not set'}
                  </p>
                </div>
                <div className="rounded-xl border border-slate-100 bg-slate-50 p-3">
                  <p className="text-[9px] font-extrabold uppercase tracking-wider text-slate-400">
                    Closing Time
                  </p>
                  <p className="mt-1 text-sm font-extrabold text-slate-700">
                    {amenityHasBookableHours
                      ? formatTime(selectedAmenity.closingTime)
                      : 'Not set'}
                  </p>
                </div>
                <div className="col-span-2 rounded-xl border border-slate-100 bg-slate-50 p-3 sm:col-span-1">
                  <p className="text-[9px] font-extrabold uppercase tracking-wider text-slate-400">
                    Capacity
                  </p>
                  <p className="mt-1 text-sm font-extrabold text-slate-700">
                    {selectedAmenity.capacity ?? 'Not limited'}
                  </p>
                </div>
              </div>

              <form
                onSubmit={handleSubmit}
                className="space-y-5 border-t border-slate-100 pt-5"
              >
                <div>
                  <h3 className="text-sm font-extrabold text-slate-800">
                    Book this amenity
                  </h3>
                  <p className="mt-1 text-[11px] font-semibold text-slate-400">
                    Choose one or more consecutive days and a time available
                    across the full date range.
                  </p>
                </div>

                <div className="space-y-2">
                  <label className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
                    Booking Type
                  </label>
                  <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                    {supportsSharedBooking && (
                      <button
                        type="button"
                        onClick={() => setIsPrivateBooking(false)}
                        className={`rounded-xl border p-3 text-left transition-colors ${
                          !isPrivateBooking
                            ? 'border-indigo-500 bg-indigo-50 text-indigo-700'
                            : 'border-slate-200 bg-white text-slate-600 hover:border-indigo-200'
                        }`}
                      >
                        <span className="block text-xs font-extrabold">
                          Shared Booking
                        </span>
                        <span className="mt-1 block text-[10px] font-semibold opacity-70">
                          Reserve your place in a shared slot.
                        </span>
                      </button>
                    )}
                    {supportsPrivateBooking && (
                      <button
                        type="button"
                        onClick={() => setIsPrivateBooking(true)}
                        className={`rounded-xl border p-3 text-left transition-colors ${
                          isPrivateBooking
                            ? 'border-indigo-500 bg-indigo-50 text-indigo-700'
                            : 'border-slate-200 bg-white text-slate-600 hover:border-indigo-200'
                        }`}
                      >
                        <span className="block text-xs font-extrabold">
                          Private Booking
                        </span>
                        <span className="mt-1 block text-[10px] font-semibold opacity-70">
                          Reserve the amenity exclusively.
                        </span>
                      </button>
                    )}
                  </div>
                </div>

                <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                  <div className="space-y-1">
                    <label className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
                      Start Date
                    </label>
                    <input
                      type="date"
                      required
                      min={todayISO()}
                      max={maximumDate}
                      value={date}
                      onChange={(event) => {
                        const nextStartDate = event.target.value;
                        setDate(nextStartDate);
                        if (endDate < nextStartDate) {
                          setEndDate(nextStartDate);
                        }
                        setFormError('');
                      }}
                      className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-xs font-semibold text-slate-700 focus:border-indigo-500 focus:bg-white focus:outline-none"
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
                      End Date
                    </label>
                    <input
                      type="date"
                      required
                      min={date || todayISO()}
                      max={maximumDate}
                      value={endDate}
                      onChange={(event) => {
                        setEndDate(event.target.value);
                        setFormError('');
                      }}
                      className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-xs font-semibold text-slate-700 focus:border-indigo-500 focus:bg-white focus:outline-none"
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
                      Time Slot
                    </label>
                    <select
                      value={timeSlot}
                      onChange={(event) => {
                        setTimeSlot(event.target.value);
                        setFormError('');
                      }}
                      disabled={
                        isCheckingSlots ||
                        Boolean(closureReason) ||
                        availableSlotValues.size === 0
                      }
                      className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-xs font-semibold text-slate-700 focus:border-indigo-500 focus:bg-white focus:outline-none disabled:text-slate-400"
                    >
                      {isCheckingSlots && (
                        <option value="">Checking availability...</option>
                      )}
                      {!isCheckingSlots && bookingSlots.length === 0 && (
                        <option value="">No time slots available</option>
                      )}
                      {!isCheckingSlots &&
                        bookingSlots.map((slot) => (
                          <option
                            key={slot.value}
                            value={slot.value}
                            disabled={!availableSlotValues.has(slot.value)}
                          >
                            {slot.label}
                            {!availableSlotValues.has(slot.value)
                              ? ' (Unavailable)'
                              : ''}
                          </option>
                        ))}
                    </select>
                  </div>
                </div>

                {bookingDates.length > 0 && (
                  <div className="flex items-center gap-2 rounded-xl border border-indigo-100 bg-indigo-50 px-3 py-2.5 text-[11px] font-bold text-indigo-700">
                    <CalendarRange className="h-4 w-4" />
                    {bookingDates.length} day
                    {bookingDates.length === 1 ? '' : 's'} selected ·{' '}
                    {formatBookingDate(bookingDates[0])}
                    {bookingDates.length > 1 &&
                      ` to ${formatBookingDate(
                        bookingDates[bookingDates.length - 1]
                      )}`}
                  </div>
                )}

                <div className="space-y-1">
                  <label className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
                    Number of Guests
                  </label>
                  <input
                    type="number"
                    min="0"
                    max={
                      selectedAmenity.capacity == null
                        ? undefined
                        : Math.max(selectedAmenity.capacity - 1, 0)
                    }
                    value={guestCount}
                    disabled={
                      !selectedAmenity.bookingSettings.allowGuestBooking
                    }
                    onChange={(event) =>
                      setGuestCount(Number(event.target.value))
                    }
                    className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-xs font-semibold text-slate-700 focus:border-indigo-500 focus:bg-white focus:outline-none disabled:cursor-not-allowed disabled:text-slate-400"
                  />
                  {!selectedAmenity.bookingSettings.allowGuestBooking && (
                    <p className="text-[10px] font-semibold text-slate-400">
                      Guests are not allowed for this amenity.
                    </p>
                  )}
                </div>

                {/* The honest answer for hours that were never set. Without
                    it, this state was an empty disabled dropdown and a dead
                    submit button with no explanation. */}
                {!amenityHasBookableHours && (
                  <div className="flex gap-2 rounded-xl border border-amber-100 bg-amber-50 p-3 text-xs font-semibold text-amber-700">
                    <AlertCircle className="h-4 w-4 shrink-0" />
                    <span>
                      This amenity has no bookable hours set yet — please
                      contact your association to have them configured.
                    </span>
                  </div>
                )}

                {(closureReason || formError) && (
                  <div className="flex gap-2 rounded-xl border border-rose-100 bg-rose-50 p-3 text-xs font-semibold text-rose-700">
                    <AlertCircle className="h-4 w-4 shrink-0" />
                    <span>{formError || closureReason}</span>
                  </div>
                )}

                {/* The slot list is a hint, and when the hint could not be
                    fetched it must not read as one. Nothing here claims a slot
                    is free — the booking write is what decides, and it answers
                    a clash with a `409` this form renders. */}
                {!closureReason &&
                  !isCheckingSlots &&
                  !isAvailabilityVerified &&
                  bookingSlots.length > 0 && (
                    <div className="flex gap-2 rounded-xl border border-slate-200 bg-slate-50 p-3 text-xs font-semibold text-slate-600">
                      <AlertCircle className="h-4 w-4 shrink-0" />
                      <span>
                        We could not check which slots are already taken. Pick
                        the one you want — you will be told straight away if it
                        has just gone.
                      </span>
                    </div>
                  )}

                {!closureReason &&
                  !isCheckingSlots &&
                  isAvailabilityVerified &&
                  bookingSlots.length > 0 &&
                  availableSlotValues.size === 0 && (
                    <div className="flex gap-2 rounded-xl border border-amber-100 bg-amber-50 p-3 text-xs font-semibold text-amber-700">
                      <AlertCircle className="h-4 w-4 shrink-0" />
                      <span>
                        No single time slot is available across all selected
                        days.
                      </span>
                    </div>
                  )}

                {(selectedAmenity.paymentSettings.bookingFee > 0 ||
                  selectedAmenity.paymentSettings.securityDeposit > 0) && (
                  <p className="rounded-xl bg-slate-50 p-3 text-[11px] font-semibold text-slate-500">
                    Booking fee: {selectedAmenity.paymentSettings.currency}{' '}
                    {selectedAmenity.paymentSettings.bookingFee}
                    {selectedAmenity.paymentSettings.securityDeposit > 0 &&
                      ` · Deposit: ${selectedAmenity.paymentSettings.currency} ${selectedAmenity.paymentSettings.securityDeposit}`}
                  </p>
                )}

                <div className="flex flex-col-reverse gap-3 border-t border-slate-100 pt-5 sm:flex-row sm:justify-end">
                  <button
                    type="button"
                    onClick={closeBookingModal}
                    disabled={isSubmitting}
                    className="rounded-xl border border-slate-200 bg-white px-5 py-2.5 text-xs font-bold text-slate-600 transition-colors hover:bg-slate-50 disabled:opacity-50"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={
                      isSubmitting ||
                      isCheckingSlots ||
                      Boolean(closureReason) ||
                      !amenityHasBookableHours ||
                      !timeSlot
                    }
                    className="flex items-center justify-center gap-1.5 rounded-xl bg-indigo-600 px-5 py-2.5 text-xs font-bold text-white shadow-md shadow-indigo-100 transition-all hover:bg-indigo-700 disabled:cursor-not-allowed disabled:bg-slate-300 disabled:shadow-none"
                  >
                    <Plus className="h-4 w-4" />
                    {isSubmitting
                      ? 'Booking...'
                      : requiresAdminApproval
                        ? `Request ${bookingDates.length}-Day Booking`
                        : `Book ${bookingDates.length} Day${
                            bookingDates.length === 1 ? '' : 's'
                          }`}
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>,
        document.body
      )}

      {managedBookingGroup && createPortal(
        <div
          className="fixed inset-0 z-[999] flex items-center justify-center bg-slate-900/60 p-4 backdrop-blur-sm"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) {
              closeCancellationModal();
            }
          }}
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="manage-booking-days-title"
            className="max-h-[92vh] w-full max-w-lg overflow-y-auto rounded-3xl bg-white p-6 shadow-xl"
          >
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2
                  id="manage-booking-days-title"
                  className="text-lg font-extrabold text-slate-900"
                >
                  Manage Booking Days
                </h2>
                <p className="mt-1 text-xs font-semibold text-slate-400">
                  Cancel only the days you no longer need. Unselected days will
                  remain booked.
                </p>
              </div>
              <button
                type="button"
                onClick={closeCancellationModal}
                disabled={isCancelling}
                aria-label="Close booking management"
                className="rounded-full bg-slate-100 p-2 text-slate-500 hover:bg-slate-200 disabled:opacity-50"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <form
              onSubmit={handlePartialCancellation}
              className="mt-6 space-y-5"
            >
              <div className="flex items-center justify-between gap-3">
                <p className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
                  Select days to cancel
                </p>
                <button
                  type="button"
                  onClick={() =>
                    setSelectedCancellationIds(
                      selectedCancellationIds.length ===
                        cancellableManagedBookings.length
                        ? []
                        : cancellableManagedBookings.map(
                            (booking) => booking.id
                          )
                    )
                  }
                  className="text-[10px] font-bold text-indigo-600 hover:text-indigo-700"
                >
                  {selectedCancellationIds.length ===
                  cancellableManagedBookings.length
                    ? 'Clear selection'
                    : 'Select all active days'}
                </button>
              </div>

              <div className="space-y-2">
                {managedBookingGroup.records.map((booking) => {
                  const canCancel = cancellableManagedBookings.some(
                    (item) => item.id === booking.id
                  );
                  const isSelected = selectedCancellationIds.includes(
                    booking.id
                  );
                  return (
                    <label
                      key={booking.id}
                      className={`flex items-center justify-between gap-4 rounded-xl border p-3 ${
                        canCancel
                          ? 'cursor-pointer border-slate-200 bg-white hover:border-rose-200'
                          : 'cursor-not-allowed border-slate-100 bg-slate-50 opacity-65'
                      }`}
                    >
                      <div className="flex items-center gap-3">
                        <input
                          type="checkbox"
                          checked={isSelected}
                          disabled={!canCancel}
                          onChange={() =>
                            setSelectedCancellationIds((current) =>
                              current.includes(booking.id)
                                ? current.filter((id) => id !== booking.id)
                                : [...current, booking.id]
                            )
                          }
                          className="h-4 w-4 rounded border-slate-300 text-rose-600 focus:ring-rose-500"
                        />
                        <div>
                          <p className="text-xs font-extrabold text-slate-700">
                            {formatBookingDate(booking.date)}
                          </p>
                          <p className="mt-0.5 text-[10px] font-semibold text-slate-400">
                            {formatInstantTime(booking.startsAt)} -{' '}
                            {formatInstantTime(booking.endsAt)}
                          </p>
                        </div>
                      </div>
                      <span
                        className={`rounded-full border px-2 py-0.5 text-[9px] font-bold ${
                          statusClassNames[booking.status] ??
                          'border-slate-200 bg-slate-50 text-slate-600'
                        }`}
                      >
                        {booking.statusLabel ?? bookingStatusLabel(booking.status)}
                      </span>
                    </label>
                  );
                })}
              </div>

              <div className="space-y-1">
                <label className="text-[10px] font-bold uppercase tracking-wider text-slate-500">
                  Cancellation reason
                </label>
                <textarea
                  required
                  rows={3}
                  value={cancellationReason}
                  onChange={(event) =>
                    setCancellationReason(event.target.value)
                  }
                  placeholder="Tell management why these days are no longer needed..."
                  className="w-full resize-none rounded-xl border border-slate-200 bg-slate-50 px-4 py-2.5 text-xs font-semibold text-slate-700 focus:border-rose-400 focus:bg-white focus:outline-none"
                />
              </div>

              {selectedCancellationIds.length > 0 && (
                <div className="flex gap-2 rounded-xl border border-amber-100 bg-amber-50 p-3 text-[11px] font-semibold text-amber-700">
                  <AlertCircle className="h-4 w-4 shrink-0" />
                  {selectedCancellationIds.length ===
                  cancellableManagedBookings.length
                    ? 'All remaining active days in this booking will be cancelled.'
                    : `${selectedCancellationIds.length} selected day${
                        selectedCancellationIds.length === 1 ? '' : 's'
                      } will be cancelled. The other days will remain active.`}
                </div>
              )}

              {cancellationError && (
                <div className="flex gap-2 rounded-xl border border-rose-100 bg-rose-50 p-3 text-xs font-semibold text-rose-700">
                  <AlertCircle className="h-4 w-4 shrink-0" />
                  {cancellationError}
                </div>
              )}

              <div className="flex flex-col-reverse gap-3 border-t border-slate-100 pt-5 sm:flex-row sm:justify-end">
                <button
                  type="button"
                  onClick={closeCancellationModal}
                  disabled={isCancelling}
                  className="rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-xs font-bold text-slate-600 hover:bg-slate-50 disabled:opacity-50"
                >
                  Keep Booking
                </button>
                <button
                  type="submit"
                  disabled={
                    isCancelling ||
                    selectedCancellationIds.length === 0 ||
                    !cancellationReason.trim()
                  }
                  className="flex items-center justify-center gap-1.5 rounded-xl bg-rose-600 px-4 py-2.5 text-xs font-bold text-white shadow-md shadow-rose-100 hover:bg-rose-700 disabled:cursor-not-allowed disabled:bg-slate-300 disabled:shadow-none"
                >
                  <Trash2 className="h-4 w-4" />
                  {isCancelling
                    ? 'Cancelling...'
                    : `Cancel ${selectedCancellationIds.length} Day${
                        selectedCancellationIds.length === 1 ? '' : 's'
                      }`}
                </button>
              </div>
            </form>
          </div>
        </div>,
        document.body
      )}
    </div>
  );
}
