import { afterEach, describe, expect, it, vi } from 'vitest';

import { subscribeToDashboard } from './dashboardApi.js';

afterEach(() => vi.unstubAllGlobals());

describe('subscribeToDashboard', () => {
  it('uses the canonical stream and closes it', () => {
    const instances = [];
    class FakeEventSource {
      constructor(url) {
        this.url = url;
        this.listeners = new Map();
        instances.push(this);
      }

      addEventListener(type, listener) {
        this.listeners.set(type, listener);
      }

      close() {
        this.closed = true;
      }
    }
    vi.stubGlobal('EventSource', FakeEventSource);
    const onChange = vi.fn();

    const unsubscribe = subscribeToDashboard(onChange);

    expect(instances[0].url).toBe('/api/v1/events');
    instances[0].listeners.get('dashboard.refresh')();
    expect(onChange).toHaveBeenCalledOnce();
    unsubscribe();
    expect(instances[0].closed).toBe(true);
  });
});
