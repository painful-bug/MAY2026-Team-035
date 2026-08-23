import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Wrench } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import LocationPicker from '../../components/common/LocationPicker';
import { workerApi } from '../../features/worker/workerApi';
import { useAuthStore } from '../../store/authStore';
import { recordServiceSignupEvent } from '../../lib/telemetry/serviceSignupTelemetry';

// The first screen a service person ever sees. Shown by the dashboard whenever
// `snapshot.provider` is null, which is the whole "has never registered" case.
//
// The first write is atomic because community search is meaningful only when
// the profile has both coordinates and at least one active skill.

export default function RegisterProvider({ provider = null }) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const identity = useAuthStore((state) => state.sessionContext?.identity);
  const refreshSession = useAuthStore((state) => state.refreshSession);
  const [form, setForm] = useState({
    displayName: provider?.displayName || identity?.full_name || '',
    headline: provider?.headline || '',
    phone: provider?.phone || '',
    serviceRadiusKm: provider?.serviceRadiusKm || 15,
  });
  const [skillIds, setSkillIds] = useState(provider?.skillIds || []);
  const [coords, setCoords] = useState({
    latitude: provider?.latitude ?? '',
    longitude: provider?.longitude ?? '',
    locationLabel: provider?.locationLabel ?? '',
  });
  const skills = useQuery({ queryKey: ['skills'], queryFn: workerApi.skills });

  const byCategory = useMemo(() => {
    const groups = new Map();
    const skillsList = Array.isArray(skills.data) ? skills.data : [];
    for (const skill of skillsList) {
      const bucket = groups.get(skill.category);
      if (bucket) bucket.push(skill);
      else groups.set(skill.category, [skill]);
    }
    return [...groups.entries()];
  }, [skills.data]);

  const register = useMutation({
    mutationFn: async () => {
      return workerApi.register({
        displayName: form.displayName.trim(),
        headline: form.headline.trim() || null,
        phone: form.phone.trim() || null,
        serviceRadiusKm: Number(form.serviceRadiusKm) || 15,
        latitude: Number(coords.latitude),
        longitude: Number(coords.longitude),
        // Optional and never load-bearing: the pair above is what proximity
        // search reads. This is only what a hiring manager's card can say.
        locationLabel: coords.locationLabel?.trim() || null,
        skillIds,
      });
    },
    onSuccess: async () => {
      void recordServiceSignupEvent('provider_profile_completed');
      await refreshSession();
      await queryClient.invalidateQueries({ queryKey: ['worker-snapshot'] });
      await queryClient.invalidateQueries({ queryKey: ['worker-profile'] });
      navigate('/worker/communities?tab=find', { replace: true });
    },
  });

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

        <LocationPicker
          value={coords}
          onChange={setCoords}
          idPrefix="provider"
          required
          legend="Where you are based"
          hint="Search for your area, or drop the pin. This is what puts you in front of nearby societies."
          labelHint="Shown to societies considering you. They never see your coordinates."
        />

        <div>
          <p className="mb-2 text-xs font-extrabold uppercase tracking-wider text-slate-500">Your trades</p>
          {skills.isPending && <p className="text-sm font-semibold text-slate-400">Loading trades…</p>}
          {skills.isError && (
            <div className="flex items-center justify-between gap-3 rounded-xl bg-rose-50 px-3 py-2">
              <p role="alert" className="text-sm font-semibold text-rose-600">{skills.error?.message || 'Could not load trades.'}</p>
              <button type="button" onClick={() => skills.refetch()} className="shrink-0 text-xs font-extrabold text-rose-700 underline">Try again</button>
            </div>
          )}
          <div className="space-y-3">
            {byCategory.map(([category, items]) => (
              <div key={category}>
                <p className="mb-1.5 text-[10px] font-bold uppercase tracking-wider text-slate-400">{category}</p>
                <div className="flex flex-wrap gap-2">
                  {items.map((skill) => (
                    <button
                      key={skill.id}
                      type="button"
                      aria-pressed={skillIds.includes(skill.id)}
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
          <p role="alert" className="rounded-xl bg-rose-50 px-4 py-3 text-sm font-semibold text-rose-700">
            {register.error?.message || 'Could not create your profile.'}
          </p>
        )}

        <button
          type="submit"
          disabled={register.isPending || skills.isPending || form.displayName.trim().length < 2 || skillIds.length === 0 || coords.latitude === '' || coords.longitude === ''}
          className="w-full rounded-xl bg-indigo-600 px-5 py-3 text-sm font-bold text-white hover:bg-indigo-700 disabled:opacity-50"
        >
          {register.isPending ? 'Saving…' : 'Next'}
        </button>
      </form>
    </div>
  );
}
