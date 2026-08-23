import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { workerApi } from '../../features/worker/workerApi';
import { useCalendarRange } from '../../features/calendar/useCalendarRange';
import CalendarMonth from '../../features/calendar/CalendarMonth';
import CalendarWeek from '../../features/calendar/CalendarWeek';
import { communityColor } from '../../lib/communityColor';
import { holdsLeadershipEngagement } from '../../lib/staffVocabulary';
import JobDetailModal from './JobDetailModal';

// The colour-coded calendar across every society that employs this person.
//
// `GET /worker/calendar` returns jobs and leave in one list on purpose, so this
// screen never draws a worker as free on a day they have booked off while a
// second request is still in flight. Nothing in the response carries a colour:
// D15 derives it from a hash of the community id, so the same society is the
// same colour here, on the manager's screen, and on the worker's other device.
//
// Department leadership is refused here in words rather than hidden from the
// nav alone (amendment 3, ruling B1). This page used to be the gap: both
// queries fired unconditionally, and `GET /worker/communities` 404s at anybody
// with no provider row — the exact defect handoff §18 ruled against on the
// landing page, never propagated here. Both queries now wait for the snapshot
// the layout already fetched (react-query deduplicates the key) and stay off
// for leadership.

export default function WorkerCalendar() {
  const range = useCalendarRange('month');
  const [openJob, setOpenJob] = useState(null);
  const snapshot = useQuery({ queryKey: ['worker-snapshot'], queryFn: workerApi.snapshot });
  const leadership = holdsLeadershipEngagement(snapshot.data?.communities);
  const entries = useQuery({
    queryKey: ['worker-calendar', range.from, range.to],
    queryFn: () => workerApi.calendar(range.from, range.to),
    enabled: snapshot.isSuccess && !leadership,
  });
  const communities = useQuery({
    queryKey: ['worker-communities'],
    queryFn: workerApi.myCommunities,
    enabled: snapshot.isSuccess && !leadership,
  });

  if (snapshot.isLoading) {
    return <p className="text-xs font-semibold text-slate-400">Loading…</p>;
  }

  if (leadership) {
    return (
      <p className="rounded-2xl border border-slate-100 bg-white p-6 text-xs font-semibold text-slate-500">
        This calendar draws a technician&apos;s booked jobs and leave, and you
        hold neither — your day is your department&apos;s queue, which is what
        the dashboard shows.
      </p>
    );
  }

  const data = entries.data ?? [];
  const legend = [...new Map((communities.data ?? []).map((c) => [c.communityId, c])).values()];

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-1">
          <button
            type="button"
            aria-label="Previous"
            onClick={range.previous}
            className="rounded-lg border border-slate-200 bg-white p-2 text-slate-500 hover:bg-slate-50"
          >
            <ChevronLeft className="h-4 w-4" />
          </button>
          <button
            type="button"
            aria-label="Next"
            onClick={range.next}
            className="rounded-lg border border-slate-200 bg-white p-2 text-slate-500 hover:bg-slate-50"
          >
            <ChevronRight className="h-4 w-4" />
          </button>
          <h1 className="ml-2 text-lg font-extrabold text-slate-900">{range.label}</h1>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={range.today}
            className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-bold text-slate-600 hover:bg-slate-50"
          >
            Today
          </button>
          <div className="flex rounded-lg border border-slate-200 bg-white p-0.5">
            {['month', 'week'].map((view) => (
              <button
                key={view}
                type="button"
                onClick={() => range.setView(view)}
                className={`rounded-md px-3 py-1.5 text-xs font-bold capitalize transition-colors ${
                  range.view === view ? 'bg-indigo-600 text-white' : 'text-slate-600 hover:bg-slate-50'
                }`}
              >
                {view}
              </button>
            ))}
          </div>
        </div>
      </div>

      {legend.length > 1 && (
        <div className="flex flex-wrap items-center gap-2">
          {legend.map((engagement) => {
            const colour = communityColor(engagement.communityId);
            return (
              <span
                key={engagement.communityId}
                className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[10px] font-bold ${colour.chip}`}
              >
                <span className={`h-1.5 w-1.5 rounded-full ${colour.dot}`} />
                {engagement.communityName}
              </span>
            );
          })}
        </div>
      )}

      {entries.isError && (
        <p className="rounded-2xl bg-rose-50 px-5 py-4 text-sm font-semibold text-rose-700">
          {entries.error?.message || 'Could not load your calendar.'}
        </p>
      )}

      {range.view === 'month' ? (
        <CalendarMonth
          days={range.days}
          entries={data}
          onSelect={(entry) => entry.workOrderId && setOpenJob(entry.workOrderId)}
          isCurrentMonth={range.isCurrentMonth}
        />
      ) : (
        <CalendarWeek
          days={range.days}
          entries={data}
          onSelect={(entry) => entry.workOrderId && setOpenJob(entry.workOrderId)}
        />
      )}

      {openJob && <JobDetailModal workOrderId={openJob} onClose={() => setOpenJob(null)} />}
    </div>
  );
}
