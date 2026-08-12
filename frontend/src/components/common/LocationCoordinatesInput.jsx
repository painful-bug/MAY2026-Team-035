import { useState } from 'react';
import { Loader2, LocateFixed } from 'lucide-react';

const FIELD = 'w-full rounded-xl border border-slate-200 px-3 py-2.5 text-sm font-medium outline-none focus:border-indigo-400';

export default function LocationCoordinatesInput({ value, onChange, idPrefix = 'location', required = false }) {
  const [locating, setLocating] = useState(false);
  const [error, setError] = useState('');

  const update = (key) => (event) => onChange({ ...value, [key]: event.target.value });
  const locate = () => {
    if (!navigator.geolocation) {
      setError('This browser does not support location. Enter the coordinates manually.');
      return;
    }
    setLocating(true);
    setError('');
    navigator.geolocation.getCurrentPosition(
      ({ coords }) => {
        onChange({ latitude: coords.latitude, longitude: coords.longitude });
        setLocating(false);
      },
      (reason) => {
        const messages = {
          1: 'Location permission was denied. Enter the coordinates manually.',
          2: 'Your location is unavailable. Try again or enter it manually.',
          3: 'Location lookup timed out. Try again or enter it manually.',
        };
        setError(messages[reason.code] || 'Could not read your location. Enter it manually.');
        setLocating(false);
      },
      { enableHighAccuracy: true, timeout: 10_000, maximumAge: 60_000 },
    );
  };

  return (
    <fieldset className="space-y-3 rounded-xl bg-slate-50 p-4">
      <legend className="px-1 text-xs font-extrabold uppercase tracking-wider text-slate-500">Location coordinates</legend>
      <p className="text-[11px] font-medium text-slate-500">Used only for distance matching. Use device location or enter latitude and longitude.</p>
      <button type="button" onClick={locate} disabled={locating} className="flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-bold text-slate-700 disabled:opacity-60">
        {locating ? <Loader2 className="h-4 w-4 animate-spin" /> : <LocateFixed className="h-4 w-4" />}
        {locating ? 'Finding location…' : error ? 'Try location again' : 'Use my location'}
      </button>
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="space-y-1" htmlFor={`${idPrefix}-latitude`}>
          <span className="text-[11px] font-bold text-slate-600">Latitude</span>
          <input id={`${idPrefix}-latitude`} type="number" inputMode="decimal" step="any" min="-90" max="90" required={required} value={value?.latitude ?? ''} onChange={update('latitude')} className={FIELD} />
        </label>
        <label className="space-y-1" htmlFor={`${idPrefix}-longitude`}>
          <span className="text-[11px] font-bold text-slate-600">Longitude</span>
          <input id={`${idPrefix}-longitude`} type="number" inputMode="decimal" step="any" min="-180" max="180" required={required} value={value?.longitude ?? ''} onChange={update('longitude')} className={FIELD} />
        </label>
      </div>
      {error ? <p role="alert" className="text-xs font-semibold text-rose-600">{error}</p> : null}
      {value?.latitude !== '' && value?.longitude !== '' && value?.latitude != null && value?.longitude != null ? (
        <p role="status" className="text-[11px] font-semibold text-emerald-700">Selected: {Number(value.latitude).toFixed(6)}, {Number(value.longitude).toFixed(6)}</p>
      ) : null}
    </fieldset>
  );
}
