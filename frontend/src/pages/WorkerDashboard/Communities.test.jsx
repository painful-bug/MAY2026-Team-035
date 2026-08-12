import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, expect, it, vi } from 'vitest';
import WorkerCommunities from './Communities';

const mocks = vi.hoisted(() => ({
  searchCommunities: vi.fn(),
  profile: vi.fn(),
  myApplications: vi.fn(),
}));

vi.mock('../../features/worker/workerApi', () => ({
  workerApi: {
    searchCommunities: mocks.searchCommunities,
    profile: mocks.profile,
    myApplications: mocks.myApplications,
  },
}));

vi.mock('../../lib/telemetry/serviceSignupTelemetry', () => ({
  recordServiceSignupEvent: vi.fn(),
}));

beforeEach(() => {
  mocks.searchCommunities.mockReset().mockResolvedValue([]);
  mocks.profile.mockReset().mockResolvedValue({ serviceRadiusKm: 15 });
  mocks.myApplications.mockReset().mockResolvedValue([]);
});

it('debounces community searches as the name is typed', async () => {
  const user = userEvent.setup();
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/worker/communities?tab=find']}>
        <WorkerCommunities />
      </MemoryRouter>
    </QueryClientProvider>,
  );

  await waitFor(() => expect(mocks.searchCommunities).toHaveBeenCalledWith({ query: '' }));
  mocks.searchCommunities.mockClear();

  await user.type(screen.getByRole('textbox'), 'Palm');

  expect(mocks.searchCommunities).not.toHaveBeenCalled();
  await waitFor(() => expect(mocks.searchCommunities).toHaveBeenCalledWith({ query: 'Palm' }));
});
