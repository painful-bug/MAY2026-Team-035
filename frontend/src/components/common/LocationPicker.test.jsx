import { useState } from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import LocationPicker from './LocationPicker';

const mocks = vi.hoisted(() => ({ search: vi.fn(), reverse: vi.fn() }));

vi.mock('../../features/geo/geoApi', () => ({
  geoApi: { search: mocks.search, reverse: mocks.reverse },
}));

// The real chunk is Leaflet, which measures a container jsdom never lays out.
// The stub keeps a handle on `onPick`, so the drag path — the one that
// re-geocodes and rewrites the suggested label — is still testable.
let pickFromMap;
vi.mock('./LocationMap', () => ({
  default: ({ onPick }) => {
    pickFromMap = onPick;
    return <div data-testid="map" />;
  },
}));

function Harness({ initial = { latitude: '', longitude: '', locationLabel: '' } }) {
  const [value, setValue] = useState(initial);
  return (
    <>
      <LocationPicker value={value} onChange={setValue} required />
      {/* A plain div, not an `<output>`: that element carries an implicit
          `status` role and would collide with the picker's own. */}
      <div data-testid="state">{JSON.stringify(value)}</div>
    </>
  );
}

const state = () => JSON.parse(screen.getByTestId('state').textContent);

const setGeolocation = (value) => Object.defineProperty(window.navigator, 'geolocation', {
  configurable: true,
  value,
});

beforeEach(() => {
  mocks.search.mockReset().mockResolvedValue([]);
  mocks.reverse.mockReset().mockResolvedValue({ label: 'Reverse geocoded place' });
  pickFromMap = undefined;
});

afterEach(() => setGeolocation(undefined));

describe('LocationPicker', () => {
  it('does not search until the search is submitted', async () => {
    const user = userEvent.setup();
    render(<Harness />);

    // Typing is not asking. Nominatim's usage policy forbids autocomplete
    // against it, so a keystroke that reached the network would be the defect
    // this assertion exists to catch.
    await user.type(screen.getByLabelText('Search for your address'), 'andheri west');
    expect(mocks.search).not.toHaveBeenCalled();

    await user.click(screen.getByRole('button', { name: 'Search' }));
    await waitFor(() => expect(mocks.search).toHaveBeenCalledTimes(1));
    expect(mocks.search).toHaveBeenCalledWith('andheri west');
  });

  it('submits the search when Enter is pressed in the field', async () => {
    const user = userEvent.setup();
    render(<Harness />);

    await user.type(screen.getByLabelText('Search for your address'), 'bandra{Enter}');

    await waitFor(() => expect(mocks.search).toHaveBeenCalledWith('bandra'));
  });

  it('fills coordinates and the label from a picked result', async () => {
    const user = userEvent.setup();
    mocks.search.mockResolvedValue([{
      label: 'Andheri West, Mumbai',
      description: 'Andheri West, Mumbai, Maharashtra, India',
      latitude: 19.1364,
      longitude: 72.8296,
    }]);
    render(<Harness />);

    await user.type(screen.getByLabelText('Search for your address'), 'andheri west');
    await user.click(screen.getByRole('button', { name: 'Search' }));
    await user.click(await screen.findByRole('button', { name: /Andheri West, Mumbai/ }));

    expect(state()).toEqual({
      latitude: 19.1364,
      longitude: 72.8296,
      locationLabel: 'Andheri West, Mumbai',
    });
    // The list closes on a pick: leaving five results under a chosen pin
    // invites a second pick that silently replaces the first.
    expect(screen.queryByRole('button', { name: /Andheri West, Mumbai/ })).toBeNull();
  });

  it('says what to do instead when address search is unavailable', async () => {
    const user = userEvent.setup();
    mocks.search.mockRejectedValue(
      Object.assign(new Error('Address search is busy.'), { code: 'geocoding_unavailable' }),
    );
    render(<Harness />);

    await user.type(screen.getByLabelText('Search for your address'), 'andheri west');
    await user.click(screen.getByRole('button', { name: 'Search' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Drop the pin on the map instead');
  });

  it('offers the map as the way out when nothing matches', async () => {
    const user = userEvent.setup();
    render(<Harness />);

    await user.type(screen.getByLabelText('Search for your address'), 'qqqzzz nowhere');
    await user.click(screen.getByRole('button', { name: 'Search' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('No match for that address');
  });

  it('keeps manual coordinate entry working', () => {
    render(<Harness />);

    fireEvent.change(screen.getByLabelText('Latitude'), { target: { value: '22.572645' } });
    fireEvent.change(screen.getByLabelText('Longitude'), { target: { value: '88.363892' } });

    expect(state()).toMatchObject({ latitude: '22.572645', longitude: '88.363892' });
    expect(screen.getByRole('status')).toHaveTextContent('22.572645, 88.363892');
    // Typed by hand, so nothing has been claimed about the name of the place.
    expect(state().locationLabel).toBe('');
  });

  it('lets the label be edited after it has been filled in', async () => {
    const user = userEvent.setup();
    render(<Harness initial={{ latitude: 19.1, longitude: 72.8, locationLabel: 'Andheri West' }} />);

    const label = screen.getByLabelText(/Location label/);
    expect(label).toHaveValue('Andheri West');
    await user.clear(label);
    await user.type(label, 'Near Andheri metro');

    expect(state().locationLabel).toBe('Near Andheri metro');
    // Editing the name must not move the pin.
    expect(state()).toMatchObject({ latitude: 19.1, longitude: 72.8 });
  });

  it('moves the pin and re-names the place when the map reports a drag', async () => {
    render(<Harness initial={{ latitude: 19.1, longitude: 72.8, locationLabel: 'Andheri West' }} />);

    pickFromMap({ latitude: 19.2, longitude: 72.9 });

    await waitFor(() => expect(state()).toEqual({
      latitude: 19.2,
      longitude: 72.9,
      locationLabel: 'Reverse geocoded place',
    }));
    expect(mocks.reverse).toHaveBeenCalledWith(19.2, 72.9);
  });

  it('keeps a dragged pin even when the reverse lookup fails', async () => {
    mocks.reverse.mockRejectedValue(new Error('busy'));
    render(<Harness initial={{ latitude: 19.1, longitude: 72.8, locationLabel: 'Andheri West' }} />);

    pickFromMap({ latitude: 19.2, longitude: 72.9 });

    // The coordinate is the fact and it survives; the name for it is a
    // courtesy and its failure is not worth an error on the form.
    await waitFor(() => expect(state()).toMatchObject({ latitude: 19.2, longitude: 72.9 }));
    expect(state().locationLabel).toBe('Andheri West');
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it('moves the pin from the device location and names it', async () => {
    const user = userEvent.setup();
    setGeolocation({
      getCurrentPosition: vi.fn((success) =>
        success({ coords: { latitude: 22.572645, longitude: 88.363892 } })),
    });
    render(<Harness />);

    await user.click(screen.getByRole('button', { name: 'Use my location' }));

    await waitFor(() => expect(state()).toEqual({
      latitude: 22.572645,
      longitude: 88.363892,
      locationLabel: 'Reverse geocoded place',
    }));
  });

  it('points at address search when location permission is denied', async () => {
    const user = userEvent.setup();
    setGeolocation({ getCurrentPosition: vi.fn((_success, error) => error({ code: 1 })) });
    render(<Harness />);

    await user.click(screen.getByRole('button', { name: 'Use my location' }));

    expect(screen.getByRole('alert')).toHaveTextContent('permission was denied');
    expect(screen.getByRole('button', { name: 'Try location again' })).toBeEnabled();
  });
});
