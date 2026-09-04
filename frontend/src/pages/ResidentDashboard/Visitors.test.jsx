import { act, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, expect, it, vi } from 'vitest';
import Visitors from './Visitors';
import { residentApi } from '../../features/resident/residentApi';

vi.mock('../../features/resident/residentApi', () => ({ residentApi: {
  visitorPasses: vi.fn(), checkoutVisitorPass: vi.fn(),
} }));
const { showToast } = vi.hoisted(() => ({ showToast: vi.fn() }));
vi.mock('../../store/appStore', () => ({ useAppStore: (select) => select({ showToast }) }));

let pass;
beforeEach(() => {
  pass = {
    id: 'pass-1', purpose: 'Guest', guestCount: 1, status: 'Checked In',
    checkedInAt: '2026-08-04T09:00:00Z', checkedOutAt: null,
    validUntil: '2026-08-04T10:00:00Z', isCurrent: true,
  };
  residentApi.visitorPasses.mockReset().mockImplementation(async ({ view }) => ({
    items: (view === 'history') === !pass.isCurrent ? [pass] : [],
  }));
  residentApi.checkoutVisitorPass.mockReset().mockImplementation(async () => {
    pass = { ...pass, status: 'Checked Out', isCurrent: false, checkedOutAt: '2026-09-04T12:00:00Z' };
    return pass;
  });
  showToast.mockReset();
});

function mount() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<MemoryRouter><QueryClientProvider client={client}><Visitors /></QueryClientProvider></MemoryRouter>);
}

it('checks out an expired checked-in visit and shows departure in History', async () => {
  mount();
  await userEvent.click(await screen.findByRole('button', { name: 'Check out', exact: true }));
  await waitFor(() => expect(residentApi.checkoutVisitorPass).toHaveBeenCalledExactlyOnceWith('pass-1'));
  await waitFor(() => expect(screen.queryByRole('button', { name: 'Check out', exact: true })).not.toBeInTheDocument());
  await userEvent.click(screen.getByRole('button', { name: 'History', exact: true }));
  expect(await screen.findByText('Checked Out', { exact: true })).toBeVisible();
  expect(screen.getByText(/^Out:/)).toBeVisible();
  expect(screen.queryByText('Still inside')).not.toBeInTheDocument();
  expect(showToast).toHaveBeenCalledWith(expect.stringContaining('Departure is recorded'), 'success');
});

it.each(['Expected', 'Approved', 'Pending Approval', 'Cancelled', 'Checked Out'])(
  'does not offer checkout for %s', async (status) => {
    pass.status = status;
    mount();
    await screen.findByRole('table');
    expect(within(screen.getByRole('table')).queryByRole('button', { name: /Check out/ })).not.toBeInTheDocument();
  }
);

it('labels group checkout and blocks duplicate requests while pending', async () => {
  pass.guestCount = 3;
  let finish;
  residentApi.checkoutVisitorPass.mockImplementation(() => new Promise((resolve) => { finish = resolve; }));
  mount();
  await userEvent.dblClick(await screen.findByRole('button', { name: 'Check out group' }));
  expect(residentApi.checkoutVisitorPass).toHaveBeenCalledOnce();
  expect(screen.getByRole('button', { name: 'Checking out…' })).toBeDisabled();
  await act(async () => finish(pass));
});

it('keeps the visit checked in on error and allows another attempt', async () => {
  residentApi.checkoutVisitorPass.mockRejectedValueOnce(new Error('Could not check out the visitor.'));
  mount();
  await userEvent.click(await screen.findByRole('button', { name: 'Check out', exact: true }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Could not check out the visitor.');
  expect(screen.getByText('Still inside')).toBeVisible();
  await userEvent.click(screen.getByRole('button', { name: 'Check out', exact: true }));
  await waitFor(() => expect(residentApi.checkoutVisitorPass).toHaveBeenCalledTimes(2));
});
