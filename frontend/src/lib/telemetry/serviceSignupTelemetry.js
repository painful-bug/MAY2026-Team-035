import { api } from '../api/client';

export async function recordServiceSignupEvent(eventName) {
  try {
    await api('/telemetry/service-signup', {
      method: 'POST', body: JSON.stringify({ eventName }),
    }, { retry: false });
  } catch {
    // Funnel telemetry is deliberately never on the product's success path.
  }
}
