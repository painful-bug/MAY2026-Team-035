import React, { useEffect } from 'react';
import {
  Activity,
  ArrowLeft,
  Building2,
  CalendarDays,
  IndianRupee,
  ShieldCheck,
  TimerReset,
} from 'lucide-react';
import { Link } from 'react-router-dom';
import KpiCard from '../components/Reports/KpiCard.jsx';
import ReportFilterBar from '../components/Reports/ReportFilterBar.jsx';
import ReportTable from '../components/Reports/ReportTable.jsx';
import { AMENITIES_ADMIN_PATH } from '../constants/amenityRoutes.js';
import { useAmenityReportsStore } from '../store/useAmenityReportsStore.js';
import { formatLedgerCurrency } from '../utils/amenityLedger.js';

export default function AmenityReportsPage() {
  const report = useAmenityReportsStore((state) => state.report);
  const filters = useAmenityReportsStore((state) => state.filters);
  const isLoading = useAmenityReportsStore((state) => state.isLoading);
  const error = useAmenityReportsStore((state) => state.error);
  const fetchReports = useAmenityReportsStore((state) => state.fetchReports);
  const setFilter = useAmenityReportsStore((state) => state.setFilter);
  const resetFilters = useAmenityReportsStore((state) => state.resetFilters);

  useEffect(() => {
    fetchReports();
  }, [fetchReports]);

  const kpis = [
    {
      label: 'Total Amenities',
      value: report.kpis.totalAmenities,
      caption: 'Facilities in scope',
      icon: Building2,
      tone: 'bg-indigo-50 text-indigo-600',
    },
    {
      label: 'Total Active Bookings',
      value: report.kpis.totalActiveBookings,
      caption: 'Approved or confirmed',
      icon: Activity,
      tone: 'bg-emerald-50 text-emerald-600',
    },
    {
      label: 'Pending Approvals',
      value: report.kpis.pendingApprovals,
      caption: 'Awaiting admin review',
      icon: TimerReset,
      tone: 'bg-amber-50 text-amber-600',
    },
    {
      label: 'Total Revenue',
      value: formatLedgerCurrency(report.kpis.totalRevenue),
      caption: 'Mock payments collected',
      icon: IndianRupee,
      tone: 'bg-emerald-50 text-emerald-600',
    },
    {
      label: 'Active Amenities',
      value: report.kpis.activeAmenities,
      caption: 'Available facilities',
      icon: ShieldCheck,
      tone: 'bg-blue-50 text-blue-600',
    },
    {
      label: 'Bookings This Month',
      value: report.kpis.bookingsThisMonth,
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
        options={report.options}
        onChange={setFilter}
        onReset={resetFilters}
      />

      {isLoading ? (
        <div className="rounded-2xl border border-slate-100 bg-white px-6 py-16 text-center text-xs font-semibold text-slate-400">
          Loading amenity reports...
        </div>
      ) : error ? (
        <div className="rounded-2xl border border-rose-100 bg-rose-50 px-6 py-14 text-center">
          <p className="text-xs font-bold text-rose-700">{error}</p>
          <button
            type="button"
            onClick={fetchReports}
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
          <ReportTable rows={report.rows} />
        </>
      )}
    </div>
  );
}
