import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Loader2, LocateFixed, Wrench } from 'lucide-react';
import { workerApi } from '../../features/worker/workerApi';

// The first screen a service person ever sees. Shown by the dashboard whenever
// `snapshot.provider` is null, which is the whole "has never registered" case.
//
// Skills are saved by a second call because they are a second endpoint
// (`PUT /service-providers/me/skills`), and they are asked for here rather than
// later because `GET /worker/communities/search` matches on them: a provider
// with no skills gets an empty search and no explanation of why.

export default function RegisterProvider() {
  const queryClient = useQueryClient();
  const [form, setForm] = useState({ displayName: '', headline: '', phone: '', serviceRadiusKm: 15 });
  const [skillIds, setSkillIds] = useState([]);
  const [coords, setCoords] = useState(null);
  const [locating, setLocating] = useState(false);
  const skills = useQuery({ queryKey: ['skills'], queryFn: workerApi.skills });

  const byCategory = useMemo(() => {
    const groups = new Map();
    for (const skill of skills.data ?? []) {
      const bucket = groups.get(skill.category);
      if (bucket) bucket.push(skill);
      else groups.set(skill.category, [skill]);
    }
    return [...groups.entries()];
  }, [skills.data]);

  const register = useMutation({
    mutationFn: async () => {
      await workerApi.register({
        displayName: form.displayName.trim(),
        headline: form.headline.trim() || null,
        phone: form.phone.trim() || null,
        serviceRadiusKm: Number(form.serviceRadiusKm) || 15,
        latitude: coords?.latitude ?? null,
        longitude: coords?.longitude ?? null,
      });
      if (skillIds.length) await workerApi.setSkills(skillIds);
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['worker-snapshot'] }),
  });

  const locate = () => {
    if (!navigator.geolocation) return;
    setLocating(true);
    navigator.geolocation.getCurrentPosition(
      (position) => {
        setCoords({ latitude: position.coords.latitude, longitude: position.coords.longitude });
        setLocating(false);
      },
      // A refused prompt is not an error worth a banner. Distance ordering just
      // sorts this provider last, which the search says it does on purpose.
      () => setLocating(false),
      { timeout: 10_000 }
    );
  };

  const toggleSkill = (id) =>
    setSkillIds((current) => (current.includes(id) ? current.filter((x) => x !== id) : [...current, id]));

  const field = 'w-full rounded-xl border border-slate-200 px-3 py-2.5 text-sm font-medium outline-none focus:border-indigo-400';

  return (
    <div className="mx-auto max-w-2xl">
      <div className="mb-6 text-center">
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-indigo-600 text-white">
          <Wrench className="h-6 w-6" />
        </div>
        <h1 className="mt-4 text-xl font-extrabold text-slate-900">Register as a service partner</h1>
        <p className="mx-auto mt-1 max-w-md text-sm font-medium text-slate-500">
          One profile works across every society that hires you. Tell us your trades and we will show you the
          communities that need them.
        </p>
      </div>

      <form
        onSubmit={(event) => {
          event.preventDefault();
          register.mutate();
        }}
        className="space-y-5 rounded-3xl border border-slate-200 bg-white p-5 sm:p-6"
      >
        <div>
          <label htmlFor="displayName" className="mb-1 block text-xs font-extrabold uppercase tracking-wider text-slate-500">
            Your name
          </label>
          <input
            id="displayName"
            required
            minLength={2}
            maxLength={120}
            value={form.displayName}
            onChange={(event) => setForm({ ...form, displayName: event.target.value })}
            className={field}
            placeholder="As residents should see it"
          />
        </div>

        <div>
          <label htmlFor="headline" className="mb-1 block text-xs font-extrabold uppercase tracking-wider text-slate-500">
            Headline <span className="font-semibold normal-case text-slate-400">optional</span>
          </label>
          <input
            id="headline"
            maxLength={160}
            value={form.headline}
            onChange={(event) => setForm({ ...form, headline: event.target.value })}
            className={field}
            placeholder="Licensed electrician, 12 years"
          />
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label htmlFor="phone" className="mb-1 block text-xs font-extrabold uppercase tracking-wider text-slate-500">
              Phone
            </label>
            <input
              id="phone"
              maxLength={20}
              value={form.phone}
              onChange={(event) => setForm({ ...form, phone: event.target.value })}
              className={field}
              placeholder="+91…"
            />
          </div>
          <div>
            <label htmlFor="radius" className="mb-1 block text-xs font-extrabold uppercase tracking-wider text-slate-500">
              How far you travel (km)
            </label>
            <input
              id="radius"
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
              {coords
                ? `Saved · ${coords.latitude.toFixed(3)}, ${coords.longitude.toFixed(3)}`
                : 'Optional. Without it you still appear, sorted last.'}
            </p>
          </div>
          <button
            type="button"
            onClick={locate}
            disabled={locating}
            className="flex shrink-0 items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-bold text-slate-700 hover:bg-slate-50 disabled:opacity-60"
          >
            {locating ? <Loader2 className="h-4 w-4 animate-spin" /> : <LocateFixed className="h-4 w-4" />}
            Use my location
          </button>
        </div>

        <div>
          <p className="mb-2 text-xs font-extrabold uppercase tracking-wider text-slate-500">Your trades</p>
          {skills.isPending && <p className="text-sm font-semibold text-slate-400">Loading trades…</p>}
          <div className="space-y-3">
            {byCategory.map(([category, items]) => (
              <div key={category}>
                <p className="mb-1.5 text-[10px] font-bold uppercase tracking-wider text-slate-400">{category}</p>
                <div className="flex flex-wrap gap-2">
                  {items.map((skill) => (
                    <button
                      key={skill.id}
                      type="button"
                      onClick={() => toggleSkill(skill.id)}
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
        </div>

        {register.isError && (
          <p className="rounded-xl bg-rose-50 px-4 py-3 text-sm font-semibold text-rose-700">
            {register.error?.message || 'Could not create your profile.'}
          </p>
        )}

        <button
          type="submit"
          disabled={register.isPending || form.displayName.trim().length < 2}
          className="w-full rounded-xl bg-indigo-600 px-5 py-3 text-sm font-bold text-white hover:bg-indigo-700 disabled:opacity-50"
        >
          {register.isPending ? 'Creating your profile…' : 'Create my profile'}
        </button>
      </form>
    </div>
  );
}
