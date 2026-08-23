import { useEffect, useRef } from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

// The map half of `LocationPicker`, in its own module so it can be the target
// of a `React.lazy` import. Leaflet plus its stylesheet is ~150 KB, and it is
// wanted on exactly three screens; every other route in the app would otherwise
// carry it. The CSS import lives here rather than in `main.jsx` for the same
// reason — a stylesheet imported from a lazy chunk ships with that chunk.
//
// A hand-rolled wrapper around plain Leaflet, not `react-leaflet`. Leaflet is
// imperative and owns its own DOM subtree, so the React-facing surface is one
// ref'd div and two effects; a binding library would add a peer-dependency
// matrix against React 19 to buy nothing this file needs.

const DEFAULT_CENTRE = [20.5937, 78.9629]; // India, roughly. Only used before a pin exists.
const DEFAULT_ZOOM = 4;
const PLACED_ZOOM = 15;

// A `divIcon` rather than Leaflet's default marker. The default resolves three
// PNGs by URL relative to the stylesheet, which every bundler breaks
// differently; this is one string, styled by the same Tailwind palette as the
// rest of the form, and has no assets to lose.
const PIN = L.divIcon({
  className: '',
  html:
    '<div style="position:relative;width:26px;height:34px">'
    + '<svg viewBox="0 0 24 32" width="26" height="34" aria-hidden="true">'
    + '<path d="M12 0C5.9 0 1 4.9 1 11c0 8.2 9.7 19.6 10.1 20.1a1.2 1.2 0 0 0 1.8 0C13.3 30.6 23 19.2 23 11 23 4.9 18.1 0 12 0z" fill="#4f46e5"/>'
    + '<circle cx="12" cy="11" r="4.2" fill="#ffffff"/>'
    + '</svg></div>',
  iconSize: [26, 34],
  iconAnchor: [13, 34],
});

export default function LocationMap({ latitude, longitude, onPick, ariaLabel }) {
  const container = useRef(null);
  const map = useRef(null);
  const marker = useRef(null);
  // The last point this component itself reported upward. Without it the effect
  // below would re-centre the map every time a drag echoed back through the
  // parent's state, which yanks the view out from under the hand doing the
  // dragging.
  const ownPick = useRef(null);
  // Effects read the latest callback without re-running: re-running would tear
  // the Leaflet map down and rebuild it on every parent render.
  const pick = useRef(onPick);
  pick.current = onPick;

  useEffect(() => {
    if (!container.current || map.current) return undefined;
    const instance = L.map(container.current, {
      center: DEFAULT_CENTRE,
      zoom: DEFAULT_ZOOM,
      // A scroll wheel over an embedded map inside a long form steals the page
      // scroll, which is the single most complained-about behaviour of embedded
      // maps. Dragging and the +/- control still zoom.
      scrollWheelZoom: false,
    });
    // Attribution is a licence condition of the tiles, not a courtesy.
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    }).addTo(instance);

    instance.on('click', (event) => {
      const point = { latitude: event.latlng.lat, longitude: event.latlng.lng };
      ownPick.current = point;
      pick.current?.(point);
    });

    map.current = instance;
    return () => {
      instance.remove();
      map.current = null;
      marker.current = null;
    };
  }, []);

  useEffect(() => {
    const instance = map.current;
    if (!instance) return;
    const lat = Number(latitude);
    const lon = Number(longitude);
    if (!Number.isFinite(lat) || !Number.isFinite(lon)) {
      if (marker.current) {
        marker.current.remove();
        marker.current = null;
      }
      return;
    }

    if (!marker.current) {
      marker.current = L.marker([lat, lon], { draggable: true, icon: PIN, keyboard: true })
        .addTo(instance);
      marker.current.on('dragend', () => {
        const { lat: draggedLat, lng: draggedLon } = marker.current.getLatLng();
        const point = { latitude: draggedLat, longitude: draggedLon };
        ownPick.current = point;
        pick.current?.(point);
      });
    } else {
      marker.current.setLatLng([lat, lon]);
    }

    const fromHere = ownPick.current
      && Math.abs(ownPick.current.latitude - lat) < 1e-9
      && Math.abs(ownPick.current.longitude - lon) < 1e-9;
    if (!fromHere) {
      instance.setView([lat, lon], Math.max(instance.getZoom(), PLACED_ZOOM));
    }
  }, [latitude, longitude]);

  return (
    <div
      ref={container}
      role="application"
      aria-label={ariaLabel || 'Map. Click or drag the pin to set the location.'}
      className="h-56 w-full overflow-hidden rounded-xl border border-slate-200 bg-slate-100 sm:h-64"
    />
  );
}
