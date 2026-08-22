import { Component, Suspense, lazy, useRef, useState } from 'react';
import { Loader2, LocateFixed, MapPin, Search } from 'lucide-react';
import { geoApi } from '../../features/geo/geoApi';

// The one way this product asks a person where something is.
//
// It replaces `LocationCoordinatesInput`, which asked for a latitude and a
// longitude and nothing else. Live testing on 2026-08-21 found what that costs:
// a latitude is not a fact anybody knows about their own house, so servicemen
// skipped the field — and a provider with no coordinates has a null generated
// `location`, which makes them invisible to every proximity search there is.
// The most hostile field on the form was the one that decided whether the
// account worked at all.
//
// Four ways in, in this order of prominence, all writing the same one pair:
//
//   1. Type an address and press Search. Explicitly NOT a type-ahead — the
//      upstream is OpenStreetMap's Nominatim, whose usage policy forbids
//      autocomplete against it. See docs/API.md §21.
//   2. Click or drag a pin on a map.
//   3. The device's own location.
//   4. The two numbers, folded away under a disclosure. Kept, because somebody
//      copying a coordinate out of another app should not have to hunt for a
//      point on a map they already know the number for.
//
// `locationLabel` rides along: a short, coarse, editable place name, filled in
// by whichever of the first two routes was used. It is optional and nothing
// computes with it — distance still comes from the coordinates. It exists so a
// hiring manager's candidate card can say "Andheri West, Mumbai" instead of
// nothing.

const LocationMap = lazy(() => import('./LocationMap'));

const FIELD = 'w-full rounded-xl border border-slate-200 px-3 py-2.5 text-sm font-medium outline-none focus:border-indigo-400';

const GEOLOCATION_ERRORS = {
  1: 'Location permission was denied. Search for your address or drop the pin instead.',
  2: 'Your location is unavailable. Search for your address or drop the pin instead.',
  3: 'Location lookup timed out. Search for your address or drop the pin instead.',
};

const isPoint = (latitude, longitude) =>
  latitude !== '' && longitude !== '' && latitude != null && longitude != null
  && Number.isFinite(Number(latitude)) && Number.isFinite(Number(longitude));

// A map is a nicety and this form is not. A chunk that fails to load — an
// offline first visit, a blocked CDN, a browser without the APIs Leaflet needs —
// must cost the person the map and nothing else, so the failure is caught here
// rather than being allowed to take the registration form down with it.
class MapBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { failed: false };
  }

  static getDerivedStateFromError() {
    return { failed: true };
  }

  render() {
    if (this.state.failed) {
      return (
        <p className="rounded-xl bg-slate-100 px-3 py-6 text-center text-xs font-semibold text-slate-500">
          The map could not be loaded. Search for your address, or enter the coordinates below.
        </p>
      );
    }
    return this.props.children;
  }
}

export default function LocationPicker({
  value,
  onChange,
  idPrefix = 'location',
  required = false,
  legend = 'Where is this?',
  hint = 'Search for the address, or drop the pin on the map. Used to match you by distance.',
  labelHint = 'Shown to people who work with you. Nobody sees your coordinates.',
}) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState(null);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState('');
  const [locating, setLocating] = useState(false);
  const [geoError, setGeoError] = useState('');

  // Every asynchronous path below (a search result, a reverse geocode landing
  // after a drag) composes its answer onto the *current* value rather than the
  // one captured when it started. Without this a reverse geocode returning
  // after the person edited the label would put the old label back.
  const latest = useRef(value);
  latest.current = value;

  const commit = (patch) => onChange({ ...latest.current, ...patch });

  const setPoint = (latitude, longitude) => commit({ latitude, longitude });

  /** Move the pin, then replace the suggested label with what is actually there. */
  const setPointAndLabel = async (latitude, longitude) => {
    setPoint(latitude, longitude);
    try {
      const place = await geoApi.reverse(latitude, longitude);
      if (place?.label) commit({ latitude, longitude, locationLabel: place.label });
    } catch {
      // The pin is the fact and it is already saved. A failed name for it is not
      // worth an error message on a form the person can finish without one.
    }
  };

  const submitSearch = async () => {
    const text = query.trim();
    if (text.length < 3) {
      setSearchError('Type at least three characters of the address.');
      return;
    }
    setSearching(true);
    setSearchError('');
    try {
      const found = await geoApi.search(text);
      setResults(found);
      if (found.length === 0) {
        setSearchError('No match for that address. Try fewer words, or drop the pin on the map.');
      }
    } catch (error) {
      setResults(null);
      setSearchError(
        error?.code === 'geocoding_unavailable'
          ? 'Address search is busy right now. Drop the pin on the map instead.'
          : error?.message || 'Could not search for that address. Drop the pin on the map instead.',
      );
    } finally {
      setSearching(false);
    }
  };

  const choose = (place) => {
    commit({
      latitude: place.latitude,
      longitude: place.longitude,
      locationLabel: place.label,
    });
    setResults(null);
    setQuery('');
  };

  const locate = () => {
    if (!navigator.geolocation) {
      setGeoError('This browser does not support location. Search for your address instead.');
      return;
    }
    setLocating(true);
    setGeoError('');
    navigator.geolocation.getCurrentPosition(
      ({ coords }) => {
        setLocating(false);
        void setPointAndLabel(coords.latitude, coords.longitude);
      },
      (reason) => {
        setGeoError(GEOLOCATION_ERRORS[reason.code] || 'Could not read your location. Search for your address instead.');
        setLocating(false);
      },
      { enableHighAccuracy: true, timeout: 10_000, maximumAge: 60_000 },
    );
  };

  const placed = isPoint(value?.latitude, value?.longitude);

  return (
    <fieldset className="space-y-3 rounded-xl bg-slate-50 p-4">
      <legend className="px-1 text-xs font-extrabold uppercase tracking-wider text-slate-500">{legend}</legend>
      <p className="text-[11px] font-medium text-slate-500">{hint}</p>

      {/* 1. Address search. A button, so it is obvious that nothing happens
          until you ask, and Enter for the people who never touch the button.
          Deliberately no onChange lookup: the upstream forbids autocomplete.

          Deliberately NOT a `<form>`, either. This component is mounted inside
          the registration form and inside the onboarding wizard, and a nested
          `<form>` is invalid HTML: the submit bubbles to the outer form, so
          pressing Search once registered the professional. */}
      <div className="flex gap-2">
        <label className="sr-only" htmlFor={`${idPrefix}-search`}>Search for your address</label>
        <input
          id={`${idPrefix}-search`}
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          onKeyDown={(event) => {
            if (event.key !== 'Enter') return;
            // Both halves matter: run the search, and stop the keypress from
            // submitting the form this picker is sitting inside.
            event.preventDefault();
            void submitSearch();
          }}
          placeholder="Andheri West, Mumbai"
          maxLength={120}
          className={FIELD}
        />
        <button
          type="button"
          onClick={() => void submitSearch()}
          disabled={searching}
          className="flex shrink-0 items-center gap-1.5 rounded-xl bg-indigo-600 px-3.5 py-2.5 text-xs font-bold text-white hover:bg-indigo-700 disabled:opacity-60"
        >
          {searching ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
          Search
        </button>
      </div>

      {results?.length ? (
        <ul className="divide-y divide-slate-200 overflow-hidden rounded-xl border border-slate-200 bg-white">
          {results.map((place) => (
            <li key={`${place.latitude},${place.longitude},${place.label}`}>
              <button
                type="button"
                onClick={() => choose(place)}
                className="flex w-full items-start gap-2 px-3 py-2.5 text-left hover:bg-slate-50"
              >
                <MapPin className="mt-0.5 h-4 w-4 shrink-0 text-indigo-500" />
                <span className="min-w-0">
                  <span className="block truncate text-sm font-bold text-slate-800">{place.label}</span>
                  <span className="block truncate text-[11px] font-medium text-slate-500">{place.description}</span>
                </span>
              </button>
            </li>
          ))}
        </ul>
      ) : null}

      {searchError ? <p role="alert" className="text-xs font-semibold text-rose-600">{searchError}</p> : null}

      {/* 2. The map. Lazy, so no other route carries Leaflet. */}
      <MapBoundary>
        <Suspense fallback={<div className="h-56 w-full animate-pulse rounded-xl bg-slate-200 sm:h-64" />}>
          <LocationMap
            latitude={value?.latitude}
            longitude={value?.longitude}
            onPick={({ latitude, longitude }) => void setPointAndLabel(latitude, longitude)}
          />
        </Suspense>
      </MapBoundary>

      {/* 3. The device. Unchanged behaviour from the widget this replaces,
          including its four error messages — they were the good part. */}
      <button
        type="button"
        onClick={locate}
        disabled={locating}
        className="flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-bold text-slate-700 disabled:opacity-60"
      >
        {locating ? <Loader2 className="h-4 w-4 animate-spin" /> : <LocateFixed className="h-4 w-4" />}
        {locating ? 'Finding location…' : geoError ? 'Try location again' : 'Use my location'}
      </button>
      {geoError ? <p role="alert" className="text-xs font-semibold text-rose-600">{geoError}</p> : null}

      {/* The label. Optional, editable, and the only field here a person reads
          back to themselves. */}
      <div className="space-y-1">
        <label className="text-[11px] font-bold text-slate-600" htmlFor={`${idPrefix}-label`}>
          Location label <span className="font-semibold normal-case text-slate-400">optional</span>
        </label>
        <input
          id={`${idPrefix}-label`}
          type="text"
          maxLength={120}
          value={value?.locationLabel ?? ''}
          onChange={(event) => commit({ locationLabel: event.target.value })}
          placeholder="Andheri West, Mumbai"
          className={FIELD}
        />
        <p className="text-[11px] font-medium text-slate-400">{labelHint}</p>
      </div>

      {/* 4. The numbers, demoted but not removed. */}
      <details className="rounded-lg border border-slate-200 bg-white px-3 py-2">
        <summary className="cursor-pointer text-[11px] font-bold text-slate-600">Enter coordinates manually</summary>
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          <label className="space-y-1" htmlFor={`${idPrefix}-latitude`}>
            <span className="text-[11px] font-bold text-slate-600">Latitude</span>
            <input
              id={`${idPrefix}-latitude`}
              type="number"
              inputMode="decimal"
              step="any"
              min="-90"
              max="90"
              required={required}
              value={value?.latitude ?? ''}
              onChange={(event) => setPoint(event.target.value, latest.current?.longitude ?? '')}
              className={FIELD}
            />
          </label>
          <label className="space-y-1" htmlFor={`${idPrefix}-longitude`}>
            <span className="text-[11px] font-bold text-slate-600">Longitude</span>
            <input
              id={`${idPrefix}-longitude`}
              type="number"
              inputMode="decimal"
              step="any"
              min="-180"
              max="180"
              required={required}
              value={value?.longitude ?? ''}
              onChange={(event) => setPoint(latest.current?.latitude ?? '', event.target.value)}
              className={FIELD}
            />
          </label>
        </div>
      </details>

      {placed ? (
        <p role="status" className="text-[11px] font-semibold text-emerald-700">
          Selected: {Number(value.latitude).toFixed(6)}, {Number(value.longitude).toFixed(6)}
        </p>
      ) : null}
    </fieldset>
  );
}
