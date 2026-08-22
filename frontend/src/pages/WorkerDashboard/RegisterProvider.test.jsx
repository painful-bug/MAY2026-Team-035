import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { createMemoryRouter, RouterProvider } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import RegisterProvider from './RegisterProvider';

const mocks = vi.hoisted(() => ({
  skills: vi.fn(),
  register: vi.fn(),
  setSkills: vi.fn(),
  refreshSession: vi.fn(),
  geoSearch: vi.fn(),
  geoReverse: vi.fn(),
}));

// The map is a lazy chunk of real Leaflet, which wants a laid-out element that
// jsdom does not give it. Stubbed here so this file keeps testing the
// registration form; `LocationPicker.test.jsx` is where the picker's own
// behaviour is asserted.
vi.mock('../../components/common/LocationMap', () => ({
  default: () => <div data-testid="map" />,
}));

vi.mock('../../features/geo/geoApi', () => ({
  geoApi: { search: mocks.geoSearch, reverse: mocks.geoReverse },
}));

vi.mock('../../features/worker/workerApi', () => ({
  workerApi: {
    skills: mocks.skills,
    register: mocks.register,
    setSkills: mocks.setSkills,
  },
}));

vi.mock('../../store/authStore', () => ({
  useAuthStore: (selector) => selector({
    sessionContext: { identity: { full_name: 'Ravi Kumar' } },
    refreshSession: mocks.refreshSession,
  }),
}));

vi.mock('../../lib/telemetry/serviceSignupTelemetry', () => ({
  recordServiceSignupEvent: vi.fn().mockResolvedValue(undefined),
}));

beforeEach(() => {
  mocks.skills.mockReset().mockResolvedValue([
    { id: 'skill-plumbing', name: 'Plumbing', category: 'maintenance' },
  ]);
  mocks.register.mockReset().mockResolvedValue({ id: 'provider-1' });
  mocks.setSkills.mockReset();
  mocks.refreshSession.mockReset().mockResolvedValue({ portal: 'worker' });
  mocks.geoSearch.mockReset().mockResolvedValue([]);
  mocks.geoReverse.mockReset().mockResolvedValue({ label: 'Indiranagar, Bengaluru' });
});

describe('RegisterProvider', () => {
  it('prefills the identity and submits profile, coordinates and skills atomically', async () => {
    const user = userEvent.setup();
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const router = createMemoryRouter([
      { path: '/worker', element: <RegisterProvider /> },
      { path: '/worker/communities', element: <p>Find work</p> },
    ], { initialEntries: ['/worker'] });
    render(
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
      </QueryClientProvider>,
    );

    expect(screen.getByLabelText('Your name')).toHaveValue('Ravi Kumar');
    await user.click(await screen.findByRole('button', { name: 'Plumbing' }));
    fireEvent.change(screen.getByLabelText('Latitude'), { target: { value: '22.572645' } });
    fireEvent.change(screen.getByLabelText('Longitude'), { target: { value: '88.363892' } });
    await user.click(screen.getByRole('button', { name: 'Next' }));

    await waitFor(() => expect(mocks.register).toHaveBeenCalledWith({
      displayName: 'Ravi Kumar',
      headline: null,
      phone: null,
      serviceRadiusKm: 15,
      latitude: 22.572645,
      longitude: 88.363892,
      // Nobody named the point, so nothing is claimed about it. The pair above
      // is what the profile needs and it is complete without a label.
      locationLabel: null,
      skillIds: ['skill-plumbing'],
    }));
    expect(mocks.setSkills).not.toHaveBeenCalled();
    await waitFor(() => expect(router.state.location.pathname).toBe('/worker/communities'));
    expect(router.state.location.search).toBe('?tab=find');
  });

  it('registers with the coordinates and label a picked address produced', async () => {
    const user = userEvent.setup();
    mocks.geoSearch.mockResolvedValue([{
      label: 'Andheri West, Mumbai',
      description: 'Andheri West, Mumbai, Maharashtra, India',
      latitude: 19.1364,
      longitude: 72.8296,
    }]);
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const router = createMemoryRouter([
      { path: '/worker', element: <RegisterProvider /> },
      { path: '/worker/communities', element: <p>Find work</p> },
    ], { initialEntries: ['/worker'] });
    render(
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
      </QueryClientProvider>,
    );

    await user.click(await screen.findByRole('button', { name: 'Plumbing' }));
    await user.type(screen.getByLabelText('Search for your address'), 'andheri west');
    await user.click(screen.getByRole('button', { name: 'Search' }));
    await user.click(await screen.findByRole('button', { name: /Andheri West, Mumbai/ }));
    await user.click(screen.getByRole('button', { name: 'Next' }));

    await waitFor(() => expect(mocks.register).toHaveBeenCalledWith(expect.objectContaining({
      latitude: 19.1364,
      longitude: 72.8296,
      locationLabel: 'Andheri West, Mumbai',
    })));
  });

  it('lets the professional retry a failed skill catalogue request', async () => {
    const user = userEvent.setup();
    mocks.skills
      .mockRejectedValueOnce(new Error('Catalogue unavailable'))
      .mockResolvedValueOnce([
        { id: 'skill-plumbing', name: 'Plumbing', category: 'maintenance' },
      ]);
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const router = createMemoryRouter([
      { path: '/worker', element: <RegisterProvider /> },
    ], { initialEntries: ['/worker'] });
    render(
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
      </QueryClientProvider>,
    );

    expect(await screen.findByRole('alert')).toHaveTextContent('Catalogue unavailable');
    await user.click(screen.getByRole('button', { name: 'Try again' }));
    expect(await screen.findByRole('button', { name: 'Plumbing' })).toBeVisible();
    expect(mocks.skills).toHaveBeenCalledTimes(2);
  });
});
