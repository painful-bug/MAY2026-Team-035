import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { MapPin, Pencil, Phone } from 'lucide-react';
import { workerApi } from '../../features/worker/workerApi';
import { AUTH_ROUTES } from '../../routes/authRoutes';

// The provider's record as others see it. Editing moved to Settings (Phase 2
// Step 6) — this page had grown a full form plus the push toggle, and its own
// comment admitted the toggle only lived here because no settings surface
// existed. Now one does, this is a view: what a manager searching for your
// trades is shown.

export default function WorkerProfile() {
  const profile = useQuery({ queryKey: ['worker-profile'], queryFn: workerApi.profile });

  if (profile.isPending) {
    return <p className="py-16 text-center text-sm font-semibold text-slate-400">Loading your profile…</p>;
  }
  if (profile.error) {
    return (
      <p role="alert" className="py-16 text-center text-sm font-semibold text-rose-600">
        {profile.error.message}
      </p>
    );
  }

  const person = profile.data;

  return (
    <div className="mx-auto max-w-2xl space-y-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-extrabold text-slate-900">Your profile</h1>
          <p className="mt-1 text-sm font-medium text-slate-500">
            One record across every society. Working in {person.communityCount}{' '}
            {person.communityCount === 1 ? 'community' : 'communities'}.
          </p>
        </div>
        <Link
          to={`${AUTH_ROUTES.WORKER_DASHBOARD}/settings`}
          className="inline-flex shrink-0 items-center gap-1.5 rounded-xl border border-slate-200 px-3.5 py-2 text-xs font-bold text-slate-600 hover:bg-slate-50"
        >
          <Pencil className="h-3.5 w-3.5" />Edit in Settings
        </Link>
      </div>

      <section className="space-y-4 rounded-3xl border border-slate-200 bg-white p-5">
        <div>
          <h2 className="text-lg font-extrabold text-slate-900">{person.displayName}</h2>
          {person.headline ? (
            <p className="text-sm font-semibold text-slate-500">{person.headline}</p>
          ) : null}
        </div>

        {person.bio ? (
          <p className="text-sm font-medium leading-relaxed text-slate-600">{person.bio}</p>
        ) : null}

        <div className="flex flex-wrap gap-4 text-xs font-semibold text-slate-500">
          {person.phone ? (
            <span className="flex items-center gap-1.5">
              <Phone className="h-4 w-4 text-slate-400" />{person.phone}
            </span>
          ) : null}
          <span className="flex items-center gap-1.5">
            <MapPin className="h-4 w-4 text-slate-400" />
            {person.latitude != null && person.longitude != null
              ? `Based at ${Number(person.latitude).toFixed(3)}, ${Number(person.longitude).toFixed(3)} · travels ${person.serviceRadiusKm} km`
              : `Travels ${person.serviceRadiusKm} km · no base location set`}
          </span>
        </div>

        <div>
          <p className="mb-2 text-xs font-extrabold uppercase tracking-wider text-slate-500">Trades</p>
          {person.skillNames.length === 0 ? (
            <p className="rounded-xl bg-amber-50 px-4 py-3 text-xs font-semibold text-amber-800">
              No trades saved — the community search matches nothing.{' '}
              <Link to={`${AUTH_ROUTES.WORKER_DASHBOARD}/settings`} className="underline">
                Add them in Settings.
              </Link>
            </p>
          ) : (
            <div className="flex flex-wrap gap-2">
              {person.skillNames.map((name) => (
                <span
                  key={name}
                  className="rounded-full border border-indigo-100 bg-indigo-50 px-3 py-1.5 text-xs font-bold text-indigo-700"
                >
                  {name}
                </span>
              ))}
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
