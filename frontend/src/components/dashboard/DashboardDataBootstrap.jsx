import { useEffect } from 'react';

import { getDashboardSnapshot, subscribeToDashboard } from '../../lib/dashboard/dashboardApi.js';
import { useAppStore } from '../../store/appStore.js';
import { useAuthStore } from '../../store/authStore.js';

export default function DashboardDataBootstrap() {
  const currentUser = useAuthStore((state) => state.currentUser);
  const isAuthReady = useAuthStore((state) => state.isAuthReady);
  const hydrateDashboard = useAppStore((state) => state.hydrateDashboard);
  const clearDashboard = useAppStore((state) => state.clearDashboard);

  useEffect(() => {
    if (!isAuthReady) return undefined;
    if (!currentUser) {
      clearDashboard();
      return undefined;
    }

    let active = true;
    let refreshTimer;
    const refresh = async () => {
      try {
        const snapshot = await getDashboardSnapshot();
        if (active) {
          hydrateDashboard(snapshot);
          window.dispatchEvent(new CustomEvent('homebandhu:dashboard-refresh'));
        }
      } catch {
        // Route guards already surface expired sessions. Keep the last valid
        // projection during a transient network failure.
      }
    };
    void refresh();
    const unsubscribe = subscribeToDashboard(() => {
      window.clearTimeout(refreshTimer);
      refreshTimer = window.setTimeout(() => void refresh(), 120);
    });
    return () => {
      active = false;
      window.clearTimeout(refreshTimer);
      unsubscribe();
    };
  }, [clearDashboard, currentUser, hydrateDashboard, isAuthReady]);

  return null;
}
