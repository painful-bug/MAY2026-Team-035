import React, { useMemo, useState } from 'react';
import { Search } from 'lucide-react';
import { formatLedgerDate } from '../../utils/amenityLedger.js';
import PaymentStatusBadge from '../Ledger/PaymentStatusBadge.jsx';
import BookingStatusBadge from '../booking/BookingStatusBadge.jsx';

const TABLE_COLUMNS = [
  'Resident',
  'Amenity',
  'Booking Date',
  'Booking Status',
  'Payment Status',
];

export default function ReportTable({ rows }) {
  const [search, setSearch] = useState('');
  const filteredRows = useMemo(() => {
    const query = search.trim().toLowerCase();
    if (!query) {
      return rows;
    }

    return rows.filter((row) =>
      [row.residentName, row.amenityName].some((value) =>
        value.toLowerCase().includes(query)
      )
    );
  }, [rows, search]);

  return (
    <section className="overflow-hidden rounded-2xl border border-slate-100 bg-white">
      <div className="flex flex-col gap-3 p-5 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-sm font-extrabold text-slate-800">
            Recent Activity
          </h2>
          <p className="mt-1 text-[11px] font-semibold text-slate-400">
            {filteredRows.length} booking records
          </p>
        </div>
        <div className="relative w-full sm:max-w-xs">
          <Search className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <input
            type="search"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search resident or amenity..."
            aria-label="Search recent activity"
            className="w-full rounded-xl border border-slate-200 bg-slate-50 py-2.5 pl-10 pr-4 text-xs font-semibold text-slate-700 placeholder:text-slate-400 focus:border-indigo-500 focus:bg-white focus:outline-none"
          />
        </div>
      </div>

      {filteredRows.length === 0 ? (
        <div className="border-t border-slate-100 px-6 py-14 text-center">
          <p className="text-sm font-extrabold text-slate-700">
            No report data available.
          </p>
          <p className="mt-1 text-xs font-semibold text-slate-400">
            Adjust the filters or search to include more booking records.
          </p>
        </div>
      ) : (
        <div className="overflow-x-auto overscroll-x-contain">
          <table className="w-full min-w-[760px] border-collapse text-left">
            <thead className="bg-slate-50">
              <tr>
                {TABLE_COLUMNS.map((column) => (
                  <th
                    key={column}
                    scope="col"
                    className="whitespace-nowrap px-4 py-3 text-[10px] font-extrabold uppercase tracking-wider text-slate-400 sm:px-5"
                  >
                    {column}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filteredRows.map((row) => (
                <tr
                  key={row.id}
                  className="border-b border-slate-50 last:border-b-0 hover:bg-slate-50/70"
                >
                  <td className="px-4 py-4 sm:px-5">
                    <p className="whitespace-nowrap text-xs font-bold text-slate-700">
                      {row.residentName}
                    </p>
                    {row.residentFlat && (
                      <p className="mt-0.5 text-[10px] font-semibold text-slate-400">
                        {row.residentFlat}
                      </p>
                    )}
                  </td>
                  <td className="whitespace-nowrap px-4 py-4 text-xs font-semibold text-slate-600 sm:px-5">
                    {row.amenityName}
                  </td>
                  <td className="whitespace-nowrap px-4 py-4 text-xs font-semibold text-slate-500 sm:px-5">
                    {formatLedgerDate(row.bookingDate)}
                  </td>
                  <td className="whitespace-nowrap px-4 py-4 sm:px-5">
                    <BookingStatusBadge status={row.bookingStatus} />
                  </td>
                  <td className="whitespace-nowrap px-4 py-4 sm:px-5">
                    {row.paymentStatus ? (
                      <PaymentStatusBadge status={row.paymentStatus} />
                    ) : (
                      <span className="text-xs font-semibold text-slate-400">
                        Not recorded
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
