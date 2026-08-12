import React, { useState } from 'react';
import {
  Activity,
  ArrowLeft,
  Building2,
  CalendarDays,
  IndianRupee,
  ShieldCheck,
  TimerReset,
} from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { amenitiesApi } from '../amenitiesApi.js';
import KpiCard from '../components/Reports/KpiCard.jsx';
import ReportFilterBar from '../components/Reports/ReportFilterBar.jsx';
import ReportTable from '../components/Reports/ReportTable.jsx';
import {
  DEFAULT_REPORT_FILTERS,
  REPORT_ALL_FILTER,
} from '../constants/amenityReports.js';
import { AMENITIES_ADMIN_PATH } from '../constants/amenityRoutes.js';
import { formatLedgerCurrency } from '../utils/amenityLedger.js';

// The reports page, over `GET /amenity-reports`.
//
// **The six tiles are no longer computed here, and that is the whole point of
// this rewrite.** `calculateAmenityReports` reduced over whatever the browser
// had loaded — three service reads stitched together in `amenityReportsService`
// — and then labelled one of the results "Total Revenue". A KPI that describes
// the page it is holding is not a KPI. `kpis` is now a database aggregate over
// every matching row while `rows` is a page, and the filters travel to the
// server so both describe the same question.
//
// `options` comes from the same response rather than from the rows: the booking
// statuses are the lifecycle's fixed vocabulary, so the filter does not lose an
// option the moment nothing currently has that status — which is exactly what
// the client-side `new Set(rows.map(...))` used to do.

const PAGE_SIZE = 100;

const EMPTY_KPIS = {
  totalAmenities: 0,
  totalActiveBookings: 0,
  pendingApprovals: 0,
  totalRevenue: 0,
  activeAmenities: 0,
  bookingsThisMonth: 0,
};

// `all` is this screen's word for "do not narrow"; the API's word for it is an
// absent parameter. Translating here keeps the select values as they were.
const toQuery = (filters) => ({
  startDate: filters.startDate || undefined,
  endDate: filters.endDate || undefined,
  amenityId:
    filters.amenityId === REPORT_ALL_FILTER ? undefined : filters.amenityId,
  bookingStatus:
    filters.bookingStatus === REPORT_ALL_FILTER
      ? undefined
      : filters.bookingStatus,
  pageSize: PAGE_SIZE,
});

export default function AmenityReportsPage() {
  const [filters, setFilters] = useState({ ...DEFAULT_REPORT_FILTERS });

  const report = useQuery({
    queryKey: ['amenities', 'reports', filters],
    queryFn: () => amenitiesApi.report(toQuery(filters)),
    // The previous page's numbers stay on screen while a filter change is in
    // flight, rather than the tiles blanking to zero and back.
    placeholderData: (previous) => previous,
  });

  const kpiValues = report.data?.kpis || EMPTY_KPIS;
  const options = report.data?.options || { amenities: [], bookingStatuses: [] };

  const kpis = [
    {
      label: 'Total Amenities',
      value: kpiValues.totalAmenities,
      caption: 'Facilities in scope',
      icon: Building2,
      tone: 'bg-indigo-50 text-indigo-600',
    },
    {
      label: 'Total Active Bookings',
      value: kpiValues.totalActiveBookings,
      caption: 'Approved or confirmed',
      icon: Activity,
      tone: 'bg-emerald-50 text-emerald-600',
    },
    {
      label: 'Pending Approvals',
      value: kpiValues.pendingApprovals,
      caption: 'Awaiting admin review',
      icon: TimerReset,
      tone: 'bg-amber-50 text-amber-600',
    },
    {
      label: 'Total Revenue',
      value: formatLedgerCurrency(kpiValues.totalRevenue),
      caption: 'Across every matching booking',
      icon: IndianRupee,
      tone: 'bg-emerald-50 text-emerald-600',
    },
    {
      label: 'Active Amenities',
      value: kpiValues.activeAmenities,
      caption: 'Available facilities',
      icon: ShieldCheck,
      tone: 'bg-blue-50 text-blue-600',
    },
    {
      label: 'Bookings This Month',
      value: kpiValues.bookingsThisMonth,
      caption: 'Current calendar month',
      icon: CalendarDays,
      tone: 'bg-indigo-50 text-indigo-600',
    },
  ];

  return (
    <div className="space-y-6">
      <header>
        <Link
          to={AMENITIES_ADMIN_PATH}
          className="inline-flex items-center gap-1.5 text-xs font-bold text-slate-500 transition-colors hover:text-indigo-600"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to amenities
        </Link>
        <h1 className="mt-4 text-2xl font-extrabold tracking-tight text-slate-900 sm:text-3xl">
          Amenity Reports
        </h1>
        <p className="mt-1 text-xs font-semibold text-slate-400">
          A lightweight summary of bookings, approvals, and revenue.
        </p>
      </header>

      <ReportFilterBar
        filters={filters}
        options={options}
        onChange={(field, value) =>
          setFilters((current) => ({ ...current, [field]: value }))
        }
        onReset={() => setFilters({ ...DEFAULT_REPORT_FILTERS })}
      />

      {report.isPending ? (
        <div className="rounded-2xl border border-slate-100 bg-white px-6 py-16 text-center text-xs font-semibold text-slate-400">
          Loading amenity reports...
        </div>
      ) : report.error ? (
        <div className="rounded-2xl border border-rose-100 bg-rose-50 px-6 py-14 text-center">
          <p role="alert" className="text-xs font-bold text-rose-700">
            {report.error.message}
          </p>
          <button
            type="button"
            onClick={() => report.refetch()}
            className="mt-3 rounded-xl border border-rose-100 bg-white px-4 py-2 text-xs font-bold text-rose-700 hover:bg-rose-50"
          >
            Try again
          </button>
        </div>
      ) : (
        <>
          <section
            aria-label="Amenity report summary"
            className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3"
          >
            {kpis.map((kpi) => (
              <KpiCard key={kpi.label} {...kpi} />
            ))}
          </section>
          <ReportTable rows={report.data?.rows || []} />
          {(report.data?.rows || []).length === PAGE_SIZE && (
            <p className="text-[11px] font-semibold text-slate-400">
              Recent activity is capped at {PAGE_SIZE} rows. The summary above
              still counts every matching booking — narrow the filters to see
              more of the table.
            </p>
          )}
        </>
      )}
    </div>
  );
}
