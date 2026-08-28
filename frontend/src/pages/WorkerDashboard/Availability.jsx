import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { QUERY_POLICIES } from '../../lib/api/queryClient';
import { Plus, Trash2 } from 'lucide-react';
import { workerApi } from '../../features/worker/workerApi';
import NoMarketplaceProfile from '../../features/worker/NoMarketplaceProfile';

// Two different things that both mean "do not send me a job", kept apart
// because they are apart in the schema and in the dispatcher.
//
// The weekly rules are the shape of a normal week and are PUT as a whole set --
// the endpoint says why: a delta API against a screen showing seven rows is a
// lost update nobody notices until somebody is booked on their day off. An
// empty set means always available, which is what never having filled this in
// already meant to `dispatch_candidates`.
//
// The blocks are one-off leave, and they are per-row because they are events
// rather than a shape.

// Sunday is 0, matching Postgres `extract(dow ...)`, which is what
// `dispatch_candidates` compares against. Displayed Monday-first because that
// is the working week; the stored number is what travels.
const WEEK = [
  { dow: 1, label: 'Monday' },
  { dow: 2, label: 'Tuesday' },
  { dow: 3, label: 'Wednesday' },
  { dow: 4, label: 'Thursday' },
  { dow: 5, label: 'Friday' },
  { dow: 6, label: 'Saturday' },
  { dow: 0, label: 'Sunday' },
];

const when = new Intl.DateTimeFormat(undefined, {
  weekday: 'short', day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit',
});

// `<input type="datetime-local">` wants a local `YYYY-MM-DDTHH:MM`, and
// `toISOString` is UTC — using it here shifts every block by the offset.
const localInputValue = (date) =>
  `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}T${String(
    date.getHours()
  ).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`;

export default function WorkerAvailability() {
  const queryClient = useQueryClient();
  // Both writes underneath this screen begin `if v_provider is null then raise
  // 'Register as a service provider first'` (`0039` 818, 847), and both reads
  // are keyed on the same provider row — so for a manager or a supervisor,
  // whom `20260812090200` admits with no provider row at all, every control
  // here is a button that 404s. They are scheduled by their department rather
  // than matched by the dispatcher; saying so is more use than a form that
  // refuses on submit.
  const snapshot = useQuery({
    queryKey: ['worker-snapshot'],
    queryFn: workerApi.snapshot,
    ...QUERY_POLICIES.snapshot,
  });
  const noMarketplaceProfile = snapshot.isSuccess && !snapshot.data?.provider;
  const rules = useQuery({
    queryKey: ['worker-rules'],
    queryFn: workerApi.availabilityRules,
    ...QUERY_POLICIES.list,
    enabled: snapshot.isSuccess && !noMarketplaceProfile,
  });
  const blocks = useQuery({
    queryKey: ['worker-unavailability'],
    queryFn: () => workerApi.unavailability(),
    ...QUERY_POLICIES.list,
    enabled: snapshot.isSuccess && !noMarketplaceProfile,
  });

  // Seven rows of local state seeded from the server, because the editor is a
  // week and the API is a set.
  const [week, setWeek] = useState({});
  useEffect(() => {
    if (!rules.data) return;
    const next = {};
    for (const rule of rules.data) {
      if (rule.scope !== 'provider') continue;
      next[rule.weekday] = {
        on: true,
        start: String(rule.startTime).slice(0, 5),
        end: String(rule.endTime).slice(0, 5),
      };
    }
    setWeek(next);
  }, [rules.data]);

  const saveRules = useMutation({
    mutationFn: () =>
      workerApi.setAvailabilityRules(
        WEEK.filter(({ dow }) => week[dow]?.on).map(({ dow }) => ({
          weekday: dow,
          startTime: week[dow].start,
          endTime: week[dow].end,
        }))
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['worker-rules'] }),
  });

  const [block, setBlock] = useState({ startsAt: '', endsAt: '', reason: '' });
  const addBlock = useMutation({
    mutationFn: () =>
      workerApi.addUnavailability({
        startsAt: new Date(block.startsAt).toISOString(),
        endsAt: new Date(block.endsAt).toISOString(),
        reason: block.reason.trim() || null,
      }),
    onSuccess: () => {
      setBlock({ startsAt: '', endsAt: '', reason: '' });
      void queryClient.invalidateQueries({ queryKey: ['worker-unavailability'] });
      void queryClient.invalidateQueries({ queryKey: ['worker-calendar'] });
    },
  });
  const removeBlock = useMutation({
    mutationFn: (id) => workerApi.removeUnavailability(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['worker-unavailability'] });
      void queryClient.invalidateQueries({ queryKey: ['worker-calendar'] });
    },
  });

  const setDay = (dow, patch) =>
    setWeek((current) => ({
      ...current,
      [dow]: { on: true, start: '09:00', end: '18:00', ...current[dow], ...patch },
    }));

  const field = 'rounded-lg border border-slate-200 px-2.5 py-1.5 text-xs font-semibold outline-none focus:border-indigo-400';

  if (noMarketplaceProfile) {
    return (
      <div className="space-y-6">
        <h1 className="text-xl font-extrabold text-slate-900">Your availability</h1>
        <NoMarketplaceProfile
          title="Your hours are your department's"
          body="The dispatcher matches hours to marketplace professionals it has to find. You were hired into a department, so your week is arranged there rather than here."
          engagements={snapshot.data?.communities}
        />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-extrabold text-slate-900">Your availability</h1>
        <p className="mt-1 text-sm font-medium text-slate-500">
          The dispatcher only offers you work inside these hours, and never during a block.
        </p>
      </div>

      <section className="rounded-3xl border border-slate-200 bg-white p-5">
        <div className="mb-4 flex items-center justify-between gap-3">
          <h2 className="text-xs font-extrabold uppercase tracking-wider text-slate-500">A normal week</h2>
          <button
            type="button"
            onClick={() => saveRules.mutate()}
            disabled={saveRules.isPending}
            className="rounded-xl bg-indigo-600 px-4 py-2 text-xs font-bold text-white hover:bg-indigo-700 disabled:opacity-50"
          >
            {saveRules.isPending ? 'Saving…' : 'Save the week'}
          </button>
        </div>

        <div className="space-y-2">
          {WEEK.map(({ dow, label }) => {
            const day = week[dow];
            return (
              <div key={dow} className="flex flex-wrap items-center gap-3 rounded-xl bg-slate-50 px-3 py-2">
                <label className="flex min-w-32 items-center gap-2 text-xs font-bold text-slate-700">
                  <input
                    type="checkbox"
                    checked={Boolean(day?.on)}
                    onChange={(event) =>
                      event.target.checked
                        ? setDay(dow, { on: true })
                        : setWeek((current) => {
                            const next = { ...current };
                            delete next[dow];
                            return next;
                          })
                    }
                    className="h-4 w-4 rounded border-slate-300"
                  />
                  {label}
                </label>
                {day?.on ? (
                  <div className="flex items-center gap-2">
                    <input
                      type="time"
                      aria-label={`${label} start`}
                      value={day.start}
                      onChange={(event) => setDay(dow, { start: event.target.value })}
                      className={field}
                    />
                    <span className="text-xs font-bold text-slate-400">to</span>
                    <input
                      type="time"
                      aria-label={`${label} end`}
                      value={day.end}
                      onChange={(event) => setDay(dow, { end: event.target.value })}
                      className={field}
                    />
                  </div>
                ) : (
                  <span className="text-xs font-semibold text-slate-400">Not working</span>
                )}
              </div>
            );
          })}
        </div>

        {Object.keys(week).length === 0 && (
          <p className="mt-3 rounded-xl bg-amber-50 px-4 py-3 text-xs font-semibold text-amber-800">
            With no days ticked you are treated as available at any hour. Tick the days you actually work to stop
            three-in-the-morning offers.
          </p>
        )}
        {saveRules.isError && (
          <p className="mt-3 rounded-xl bg-rose-50 px-4 py-3 text-xs font-semibold text-rose-700">
            {saveRules.error?.message || 'Could not save your week.'}
          </p>
        )}
      </section>

      <section className="rounded-3xl border border-slate-200 bg-white p-5">
        <h2 className="mb-4 text-xs font-extrabold uppercase tracking-wider text-slate-500">Time off</h2>

        <form
          onSubmit={(event) => {
            event.preventDefault();
            addBlock.mutate();
          }}
          className="mb-4 grid gap-3 sm:grid-cols-[1fr_1fr_1.4fr_auto]"
        >
          <input
            type="datetime-local"
            required
            aria-label="Block starts"
            min={localInputValue(new Date())}
            value={block.startsAt}
            onChange={(event) => setBlock({ ...block, startsAt: event.target.value })}
            className={field}
          />
          <input
            type="datetime-local"
            required
            aria-label="Block ends"
            min={block.startsAt || localInputValue(new Date())}
            value={block.endsAt}
            onChange={(event) => setBlock({ ...block, endsAt: event.target.value })}
            className={field}
          />
          <input
            maxLength={300}
            aria-label="Reason"
            placeholder="Reason (optional)"
            value={block.reason}
            onChange={(event) => setBlock({ ...block, reason: event.target.value })}
            className={field}
          />
          <button
            type="submit"
            disabled={addBlock.isPending || !block.startsAt || !block.endsAt}
            className="flex items-center justify-center gap-1.5 rounded-lg bg-slate-900 px-4 py-1.5 text-xs font-bold text-white hover:bg-slate-800 disabled:opacity-50"
          >
            <Plus className="h-3.5 w-3.5" />
            Block
          </button>
        </form>

        {addBlock.isError && (
          <p className="mb-3 rounded-xl bg-rose-50 px-4 py-3 text-xs font-semibold text-rose-700">
            {addBlock.error?.message || 'Could not save that block.'}
          </p>
        )}

        <div className="space-y-2">
          {(blocks.data ?? []).length === 0 && (
            <p className="py-4 text-center text-xs font-semibold text-slate-400">No time off booked.</p>
          )}
          {(blocks.data ?? []).map((item) => (
            <div key={item.id} className="flex items-center justify-between gap-3 rounded-xl bg-slate-50 px-3 py-2.5">
              <div className="min-w-0">
                <p className="truncate text-xs font-bold text-slate-800">
                  {when.format(new Date(item.startsAt))} → {when.format(new Date(item.endsAt))}
                </p>
                <p className="truncate text-[11px] font-medium text-slate-500">
                  {item.reason || 'No reason given'}
                  {item.scope !== 'provider' && ` · set by ${item.departmentName || 'a department'}`}
                </p>
              </div>
              {/* Only the worker's own blocks are theirs to delete. A row a
                  department recorded against one roster is not. */}
              {item.scope === 'provider' && (
                <button
                  type="button"
                  aria-label="Remove block"
                  onClick={() => removeBlock.mutate(item.id)}
                  disabled={removeBlock.isPending}
                  className="rounded-lg p-2 text-slate-400 hover:bg-rose-50 hover:text-rose-600 disabled:opacity-50"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              )}
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
