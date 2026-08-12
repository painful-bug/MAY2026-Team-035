import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Bell,
  BellOff,
  Building2,
  CalendarClock,
  Loader2,
  LocateFixed,
  LogOut,
  X,
} from 'lucide-react';
import { workerApi } from '../../features/worker/workerApi';
import { useAuthStore } from '../../store/authStore';
import { communityColor } from '../../lib/communityColor';
import { disablePush, enablePush, pushEnabled, pushSupported } from '../../lib/push/pushClient';

// The settings surface the doc asked for: everything about the person except
// their name and email — those are identity, shown read-only with the reason —
// plus the push toggle (whose old home in Profile.jsx said it belonged here)
// and the ask-to-leave flow, one card per community, each with a proper modal:
// leave immediately, or on a date.

const field =
  'w-full rounded-xl border border-slate-200 px-3 py-2.5 text-sm font-medium outline-none focus:border-indigo-400';

const dayText = (value) => {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? null
    : date.toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' });
};

function PushCard() {
  const [state, setState] = useState({ on: false, busy: true, error: '' });

  useEffect(() => {
    void pushEnabled().then((on) => setState({ on, busy: false, error: '' }));
  }, []);

  const toggle = async () => {
    setState((current) => ({ ...current, busy: true, error: '' }));
    const result = state.on ? await disablePush() : await enablePush();
    setState({ on: result.ok ? !state.on : state.on, busy: false, error: result.ok ? '' : result.reason });
  };

  if (!pushSupported()) {
    return (
      <section className="rounded-2xl border border-slate-200 bg-white p-4">
        <p className="text-xs font-extrabold text-slate-700">Job alerts</p>
        <p className="mt-1 text-[11px] font-medium text-slate-500">
          This browser cannot receive push notifications. Offers still appear on your dashboard.
        </p>
      </section>
    );
  }

  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-4">
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-extrabold text-slate-700">Job alerts</p>
          <p className="mt-0.5 text-[11px] font-medium text-slate-500">
            {state.on ? 'This device buzzes when an offer arrives.' : 'Offers arrive silently on this device.'}
          </p>
        </div>
        <button
          type="button"
          onClick={toggle}
          disabled={state.busy}
          className={`flex shrink-0 items-center gap-2 rounded-lg px-3 py-2 text-xs font-bold disabled:opacity-60 ${
            state.on ? 'bg-emerald-50 text-emerald-700' : 'border border-slate-200 text-slate-700 hover:bg-slate-50'
          }`}
        >
          {state.busy ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : state.on ? (
            <Bell className="h-4 w-4" />
          ) : (
            <BellOff className="h-4 w-4" />
          )}
          {state.on ? 'On' : 'Turn on'}
        </button>
      </div>
      {state.error && <p className="mt-2 text-[11px] font-semibold text-rose-700">{state.error}</p>}
    </section>
  );
}

// Leave: immediately, or on a date. A modal rather than window.prompt because
// a date is not a string somebody should type freehand — and because the
// manager's decision releases booked work from that date, so the date IS the
// request.
function LeaveModal({ engagement, busy, error, onSubmit, onClose }) {
  const [mode, setMode] = useState('date');
  const [date, setDate] = useState('');
  const [reason, setReason] = useState('');

  useEffect(() => {
    const onKey = (event) => {
      if (event.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', onKey);
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', onKey);
      document.body.style.overflow = '';
    };
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-[999] flex items-center justify-center bg-slate-900/60 p-4 backdrop-blur-sm"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div className="w-full max-w-md rounded-3xl bg-white p-6 shadow-xl">
        <div className="flex items-start justify-between">
          <div>
            <h2 className="text-lg font-extrabold text-slate-900">
              Leave {engagement.communityName}
            </h2>
            <p className="mt-1 text-xs font-semibold text-slate-400">
              Your manager decides. Until then you keep working — but no new work
              on or after your leave date will reach you.
            </p>
          </div>
          <button type="button" onClick={onClose} className="rounded-full bg-slate-100 p-2">
            <X className="h-4 w-4 text-slate-500" />
          </button>
        </div>

        <div className="mt-5 space-y-2">
          <label className="flex items-center gap-3 rounded-xl border border-slate-200 p-3 text-xs font-bold text-slate-700">
            <input type="radio" checked={mode === 'date'} onChange={() => setMode('date')} />
            On a date
            {mode === 'date' && (
              <input
                type="date"
                value={date}
                min={new Date(Date.now() + 86_400_000).toISOString().slice(0, 10)}
                onChange={(event) => setDate(event.target.value)}
                className={`${field} ml-auto max-w-[10rem] text-xs`}
              />
            )}
          </label>
          <label className="flex items-center gap-3 rounded-xl border border-slate-200 p-3 text-xs font-bold text-slate-700">
            <input
              type="radio"
              checked={mode === 'immediate'}
              onChange={() => setMode('immediate')}
            />
            Immediately
          </label>
          <textarea
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            placeholder="Why are you leaving? (optional)"
            rows={2}
            maxLength={500}
            className={field}
          />
        </div>

        {error ? (
          <p role="alert" className="mt-3 text-xs font-semibold text-rose-600">{error.message}</p>
        ) : null}

        <button
          type="button"
          disabled={busy || (mode === 'date' && !date)}
          onClick={() =>
            onSubmit({
              reason: reason.trim() || null,
              effectiveAt:
                mode === 'date' && date ? new Date(`${date}T00:00:00`).toISOString() : null,
            })
          }
          className="mt-4 w-full rounded-xl bg-rose-600 py-2.5 text-xs font-bold text-white hover:bg-rose-700 disabled:opacity-50"
        >
          {busy ? 'Sending…' : 'Ask to leave'}
        </button>
      </div>
    </div>
  );
}

function LeaveSection() {
  const queryClient = useQueryClient();
  const engagements = useQuery({ queryKey: ['worker-communities'], queryFn: workerApi.myCommunities });
  const [leaving, setLeaving] = useState(null);

  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ['worker-communities'] });
    void queryClient.invalidateQueries({ queryKey: ['worker-snapshot'] });
  };

  const request = useMutation({
    mutationFn: ({ staffId, reason, effectiveAt }) =>
      workerApi.requestDeparture(staffId, reason, effectiveAt),
    onSuccess: () => {
      setLeaving(null);
      refresh();
    },
  });
  const cancel = useMutation({
    mutationFn: (staffId) => workerApi.cancelDeparture(staffId),
    onSuccess: refresh,
  });

  const rows = (engagements.data || []).filter((row) => row.status === 'active');
  if (engagements.isLoading || rows.length === 0) return null;

  return (
    <section className="space-y-3 rounded-2xl border border-slate-200 bg-white p-4">
      <p className="text-xs font-extrabold text-slate-700">Leaving a community</p>
      <p className="text-[11px] font-medium text-slate-500">
        A manager approves every leave. Work booked from your leave date onward is
        reassigned by the community once they do.
      </p>
      {rows.map((row) => {
        const departure = row.departure;
        return (
          <div
            key={row.staffAssignmentId}
            className={`space-y-2 rounded-xl border border-slate-200 border-l-4 p-3 ${communityColor(row.communityId).bar}`}
          >
            <div className="flex items-center gap-2">
              <Building2 className="h-4 w-4 text-slate-400" />
              <p className="text-xs font-extrabold text-slate-800">{row.communityName}</p>
              <span className="text-[10px] font-semibold text-slate-400">{row.departmentName}</span>
            </div>
            {departure ? (
              <div className="flex flex-wrap items-center gap-2">
                <p className="flex items-center gap-1.5 text-[11px] font-bold text-amber-700">
                  <CalendarClock className="h-3.5 w-3.5" />
                  {departure.status === 'approved' && departure.effectiveAt
                    ? `Approved — you leave ${dayText(departure.effectiveAt)}.`
                    : departure.requestedEffectiveAt
                      ? `Asked to leave ${dayText(departure.requestedEffectiveAt)}. Waiting on the manager.`
                      : 'Asked to leave immediately. Waiting on the manager.'}
                </p>
                {departure.status === 'pending' ? (
                  <button
                    type="button"
                    disabled={cancel.isPending}
                    onClick={() => cancel.mutate(row.staffAssignmentId)}
                    className="ml-auto rounded-lg border border-slate-200 px-3 py-1.5 text-[11px] font-bold text-slate-600 hover:bg-slate-50 disabled:opacity-60"
                  >
                    Stay after all
                  </button>
                ) : null}
              </div>
            ) : (
              <button
                type="button"
                onClick={() => setLeaving(row)}
                className="inline-flex items-center gap-1.5 rounded-lg border border-rose-200 px-3 py-1.5 text-[11px] font-bold text-rose-700 hover:bg-rose-50"
              >
                <LogOut className="h-3.5 w-3.5" />Ask to leave
              </button>
            )}
          </div>
        );
      })}
      {cancel.error ? (
        <p role="alert" className="text-xs font-semibold text-rose-600">{cancel.error.message}</p>
      ) : null}

      {leaving ? (
        <LeaveModal
          engagement={leaving}
          busy={request.isPending}
          error={request.error}
          onSubmit={(payload) => request.mutate({ staffId: leaving.staffAssignmentId, ...payload })}
          onClose={() => setLeaving(null)}
        />
      ) : null}
    </section>
  );
}

export default function WorkerSettings() {
  const queryClient = useQueryClient();
  const sessionContext = useAuthStore((state) => state.sessionContext);
  const profile = useQuery({ queryKey: ['worker-profile'], queryFn: workerApi.profile });
  const skills = useQuery({ queryKey: ['skills'], queryFn: workerApi.skills });

  const [form, setForm] = useState(null);
  const [skillIds, setSkillIds] = useState([]);
  const [locating, setLocating] = useState(false);

  useEffect(() => {
    if (!profile.data) return;
    setForm({
      headline: profile.data.headline ?? '',
      bio: profile.data.bio ?? '',
      phone: profile.data.phone ?? '',
      serviceRadiusKm: profile.data.serviceRadiusKm ?? 15,
      latitude: profile.data.latitude ?? null,
      longitude: profile.data.longitude ?? null,
    });
    setSkillIds(profile.data.skillIds ?? []);
  }, [profile.data]);

  const byCategory = useMemo(() => {
    const groups = new Map();
    for (const skill of skills.data ?? []) {
      const bucket = groups.get(skill.category);
      if (bucket) bucket.push(skill);
      else groups.set(skill.category, [skill]);
    }
    return [...groups.entries()];
  }, [skills.data]);

  const save = useMutation({
    mutationFn: async () => {
      // No displayName here, and none accepted: the name is identity, not a
      // setting (PATCH /service-providers/me refuses the field since 0045).
      await workerApi.updateProfile({
        headline: form.headline.trim() || null,
        bio: form.bio.trim() || null,
        phone: form.phone.trim() || null,
        serviceRadiusKm: Number(form.serviceRadiusKm) || 15,
        latitude: form.latitude,
        longitude: form.longitude,
      });
      await workerApi.setSkills(skillIds);
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['worker-profile'] });
      void queryClient.invalidateQueries({ queryKey: ['worker-snapshot'] });
      void queryClient.invalidateQueries({ queryKey: ['worker-community-search'] });
    },
  });

  const locate = () => {
    if (!navigator.geolocation) return;
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      (position) => {
        setForm((current) => ({
          ...current,
          latitude: position.coords.latitude,
          longitude: position.coords.longitude,
        }));
        setLocating(false);
      },
      () => setLocating(false),
      { timeout: 10_000 }
    );
  };

  if (profile.isPending || !form) {
    return <p className="py-16 text-center text-sm font-semibold text-slate-400">Loading settings…</p>;
  }

  return (
    <div className="mx-auto max-w-2xl space-y-5">
      <div>
        <h1 className="text-xl font-extrabold text-slate-900">Settings</h1>
        <p className="mt-1 text-sm font-medium text-slate-500">
          Your details, alerts, and leaving.
        </p>
      </div>

      {/* Identity: shown, never edited here. */}
      <section className="rounded-2xl border border-slate-200 bg-white p-4">
        <p className="text-xs font-extrabold text-slate-700">Account</p>
        <div className="mt-2 grid gap-3 sm:grid-cols-2">
          <div>
            <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Name</p>
            <p className="text-sm font-semibold text-slate-700">{profile.data.displayName}</p>
          </div>
          <div>
            <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Email</p>
            <p className="truncate text-sm font-semibold text-slate-700">
              {sessionContext?.identity?.email || '—'}
            </p>
          </div>
        </div>
        <p className="mt-2 text-[11px] font-medium text-slate-400">
          Name and email are your identity across every community and cannot be
          changed here.
        </p>
      </section>

      <PushCard />

      <form
        onSubmit={(event) => {
          event.preventDefault();
          save.mutate();
        }}
        className="space-y-5 rounded-3xl border border-slate-200 bg-white p-5"
      >
        <div>
          <label htmlFor="s-headline" className="mb-1 block text-xs font-extrabold uppercase tracking-wider text-slate-500">
            Headline
          </label>
          <input
            id="s-headline"
            maxLength={160}
            value={form.headline}
            onChange={(event) => setForm({ ...form, headline: event.target.value })}
            className={field}
          />
        </div>

        <div>
          <label htmlFor="s-bio" className="mb-1 block text-xs font-extrabold uppercase tracking-wider text-slate-500">
            About your work
          </label>
          <textarea
            id="s-bio"
            rows={3}
            maxLength={2000}
            value={form.bio}
            onChange={(event) => setForm({ ...form, bio: event.target.value })}
            className={field}
          />
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label htmlFor="s-phone" className="mb-1 block text-xs font-extrabold uppercase tracking-wider text-slate-500">
              Phone
            </label>
            <input
              id="s-phone"
              maxLength={20}
              value={form.phone}
              onChange={(event) => setForm({ ...form, phone: event.target.value })}
              className={field}
            />
          </div>
          <div>
            <label htmlFor="s-radius" className="mb-1 block text-xs font-extrabold uppercase tracking-wider text-slate-500">
              How far you travel (km)
            </label>
            <input
              id="s-radius"
              type="number"
              min={1}
              max={500}
              value={form.serviceRadiusKm}
              onChange={(event) => setForm({ ...form, serviceRadiusKm: event.target.value })}
              className={field}
            />
          </div>
        </div>

        <div className="flex items-center justify-between rounded-xl bg-slate-50 px-4 py-3">
          <div className="min-w-0">
            <p className="text-xs font-extrabold text-slate-700">Where you are based</p>
            <p className="text-[11px] font-medium text-slate-500">
              {form.latitude != null && form.longitude != null
                ? `${Number(form.latitude).toFixed(3)}, ${Number(form.longitude).toFixed(3)}`
                : 'Not set. Community search sorts you last without it.'}
            </p>
          </div>
          <button
            type="button"
            onClick={locate}
            disabled={locating}
            className="flex shrink-0 items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-bold text-slate-700 hover:bg-slate-50 disabled:opacity-60"
          >
            {locating ? <Loader2 className="h-4 w-4 animate-spin" /> : <LocateFixed className="h-4 w-4" />}
            Update
          </button>
        </div>

        <div>
          <p className="mb-2 text-xs font-extrabold uppercase tracking-wider text-slate-500">Your trades</p>
          <div className="space-y-3">
            {byCategory.map(([category, items]) => (
              <div key={category}>
                <p className="mb-1.5 text-[10px] font-bold uppercase tracking-wider text-slate-400">{category}</p>
                <div className="flex flex-wrap gap-2">
                  {items.map((skill) => (
                    <button
                      key={skill.id}
                      type="button"
                      onClick={() =>
                        setSkillIds((current) =>
                          current.includes(skill.id)
                            ? current.filter((id) => id !== skill.id)
                            : [...current, skill.id]
                        )
                      }
                      className={`rounded-full border px-3 py-1.5 text-xs font-bold transition-colors ${
                        skillIds.includes(skill.id)
                          ? 'border-indigo-600 bg-indigo-600 text-white'
                          : 'border-slate-200 bg-white text-slate-600 hover:bg-slate-50'
                      }`}
                    >
                      {skill.name}
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
          {skillIds.length === 0 && (
            <p className="mt-2 rounded-xl bg-amber-50 px-4 py-3 text-xs font-semibold text-amber-800">
              With no trades saved, the community search matches nothing and no supervisor can be offered you.
            </p>
          )}
        </div>

        {save.isError && (
          <p className="rounded-xl bg-rose-50 px-4 py-3 text-sm font-semibold text-rose-700">
            {save.error?.message || 'Could not save.'}
          </p>
        )}
        {save.isSuccess && !save.isPending && (
          <p className="rounded-xl bg-emerald-50 px-4 py-3 text-sm font-semibold text-emerald-700">Saved.</p>
        )}

        <button
          type="submit"
          disabled={save.isPending}
          className="w-full rounded-xl bg-indigo-600 px-5 py-3 text-sm font-bold text-white hover:bg-indigo-700 disabled:opacity-50"
        >
          {save.isPending ? 'Saving…' : 'Save changes'}
        </button>
      </form>

      <LeaveSection />
    </div>
  );
}
