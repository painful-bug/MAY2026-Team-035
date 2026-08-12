import { useState } from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import LocationCoordinatesInput from './LocationCoordinatesInput';

function Harness() {
  const [value, setValue] = useState({ latitude: '', longitude: '' });
  return <LocationCoordinatesInput value={value} onChange={setValue} required />;
}

const setGeolocation = (value) => Object.defineProperty(window.navigator, 'geolocation', {
  configurable: true,
  value,
});

afterEach(() => setGeolocation(undefined));

describe('LocationCoordinatesInput', () => {
  it('fills and displays coordinates from browser GPS', async () => {
    setGeolocation({
      getCurrentPosition: vi.fn((success) => success({ coords: { latitude: 22.572645, longitude: 88.363892 } })),
    });
    render(<Harness />);
    await userEvent.click(screen.getByRole('button', { name: 'Use my location' }));
    expect(screen.getByLabelText('Latitude')).toHaveValue(22.572645);
    expect(screen.getByRole('status')).toHaveTextContent('22.572645, 88.363892');
  });

  it('keeps manual entry available when permission is denied', async () => {
    const user = userEvent.setup();
    setGeolocation({ getCurrentPosition: vi.fn((_success, error) => error({ code: 1 })) });
    render(<Harness />);
    await user.click(screen.getByRole('button', { name: 'Use my location' }));
    expect(screen.getByRole('alert')).toHaveTextContent('permission was denied');
    await user.type(screen.getByLabelText('Latitude'), '22.5');
    await user.type(screen.getByLabelText('Longitude'), '88.3');
    expect(screen.getByLabelText('Latitude')).toHaveValue(22.5);
    expect(screen.getByLabelText('Longitude')).toHaveValue(88.3);
  });

  it('explains the fallback when geolocation is unsupported', async () => {
    setGeolocation(undefined);
    render(<Harness />);
    await userEvent.click(screen.getByRole('button', { name: 'Use my location' }));
    expect(screen.getByRole('alert')).toHaveTextContent('does not support location');
  });

  it('keeps retry and manual coordinates available after a GPS timeout', async () => {
    const locate = vi.fn((_success, error) => error({ code: 3 }));
    setGeolocation({ getCurrentPosition: locate });
    render(<Harness />);

    await userEvent.click(screen.getByRole('button', { name: 'Use my location' }));
    expect(screen.getByRole('alert')).toHaveTextContent('timed out');
    await userEvent.click(screen.getByRole('button', { name: 'Try location again' }));
    expect(locate).toHaveBeenCalledTimes(2);
    expect(screen.getByLabelText('Latitude')).toBeEnabled();
  });
});
