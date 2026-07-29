import { api } from '../api/client.js';

export const getDashboardSnapshot = () => api('/dashboard/snapshot');

export function subscribeToDashboard(onChange) {
  const source = new EventSource('/api/v1/dashboard/events');
  const refresh = () => onChange();
  source.addEventListener('dashboard.refresh', refresh);
  source.addEventListener('message', refresh);
  return () => source.close();
}
