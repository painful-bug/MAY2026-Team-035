import { api } from '../../lib/api/client';

// The two reads behind `LocationPicker`, in one thin file — same shape as
// `features/worker/workerApi.js`: no state, no caching, no error translation.
//
// Both go to our own backend, which proxies OpenStreetMap's Nominatim. They are
// deliberately NOT called from a `useEffect` on the query string. The upstream's
// usage policy forbids autocomplete against it, so `search` is wired to a button
// and to Enter, and nothing else may call it. See docs/API.md §21.
export const geoApi = {
  search: (query) => api(`/geo/search?q=${encodeURIComponent(query.trim())}`),
  reverse: (latitude, longitude) =>
    api(`/geo/reverse?lat=${encodeURIComponent(latitude)}&lon=${encodeURIComponent(longitude)}`),
};
