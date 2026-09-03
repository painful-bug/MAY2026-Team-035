import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { beforeEach, expect, it, vi } from 'vitest';
import GateHome from './GateHome';
import { securityApi } from '../../features/security/securityApi';
import { useOfflineGate } from '../../features/security/offline/useOfflineGate';

vi.mock('../../features/security/securityApi', () => ({ securityApi: { verify: vi.fn() } }));
vi.mock('../../features/security/offline/useOfflineGate', () => ({ useOfflineGate: vi.fn() }));
vi.mock('../../features/security/components/VerdictCard', () => ({
  default: ({ verdict, provisional }) => verdict
    ? <p>{provisional ? 'Provisional result' : 'Confirmed result'}</p> : null,
}));

let gate;
beforeEach(() => {
  gate = {
    online: true,
    pending: [],
    rejected: [],
    bundle: { passes: [] },
    bundleQuery: { isPending: false },
    bundleUsable: true,
    verifyOffline: vi.fn(),
  };
  useOfflineGate.mockReturnValue(gate);
  securityApi.verify.mockReset();
});

it.each(['online', 'offline', 'network failure'])(
  'keeps verification pending and blocks duplicates through the %s path', async (mode) => {
    let finish;
    const pending = new Promise((resolve) => { finish = resolve; });
    if (mode === 'online') securityApi.verify.mockReturnValue(pending);
    else {
      gate.online = mode !== 'offline';
      securityApi.verify.mockRejectedValue(new Error('network failed'));
      gate.verifyOffline.mockReturnValue(pending);
    }
    const client = new QueryClient({ defaultOptions: { mutations: { retry: 2 } } });
    render(<QueryClientProvider client={client}><GateHome /></QueryClientProvider>);
    await userEvent.type(screen.getByPlaceholderText('Security code'), '123456');
    await userEvent.dblClick(screen.getByRole('button', { name: 'Verify' }));
    expect(screen.getByRole('button', { name: 'Checking…' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Start QR camera scanner' })).toBeDisabled();
    if (mode === 'offline') expect(securityApi.verify).not.toHaveBeenCalled();
    else expect(securityApi.verify).toHaveBeenCalledExactlyOnceWith({ credential: '123456' });
    if (mode !== 'online') expect(gate.verifyOffline).toHaveBeenCalledExactlyOnceWith('123456');
    await act(async () => finish({ verdict: 'admitted' }));
    expect(await screen.findByText(mode === 'online' ? 'Confirmed result' : 'Provisional result')).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole('button', { name: 'Verify' })).toBeEnabled());
    client.clear();
  }
);

it('surfaces a failed offline verification without retrying a gate operation', async () => {
  gate.online = false;
  gate.verifyOffline.mockRejectedValue(new Error('cache unavailable'));
  const client = new QueryClient({ defaultOptions: { mutations: { retry: 2, retryDelay: 0 } } });
  render(<QueryClientProvider client={client}><GateHome /></QueryClientProvider>);
  await userEvent.type(screen.getByPlaceholderText('Security code'), '123456');
  await userEvent.click(screen.getByRole('button', { name: 'Verify' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('The pass could not be verified');
  expect(gate.verifyOffline).toHaveBeenCalledOnce();
  client.clear();
});
