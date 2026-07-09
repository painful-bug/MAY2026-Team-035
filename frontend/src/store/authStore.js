import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import { useAppStore } from './appStore';

// Auth is scoped per-tab on purpose: currentUser persists to sessionStorage, so
// a resident tab and an admin tab stay independently logged in (both reading the
// same shared domain data from useAppStore). login/logout reach into the app
// store at call time (not import time) — the circular import is safe because
// nothing crosses stores during module evaluation.
export const useAuthStore = create(
  persist(
    (set) => ({
      currentUser: null,
      setCurrentUser: (currentUser) => set({ currentUser }),

      // Simulated OTP login: matches phone against the users directory (+ two
      // demo shortcut numbers). The OTP itself is not verified.
      login: (phone) => {
        const app = useAppStore.getState();
        const users = app.users;
        const cleanPhone = phone.trim().replace(/\s+/g, '');

        const foundUser = users.find((u) => {
          const uPhone = u.phone.trim().replace(/\s+/g, '');
          return uPhone.includes(cleanPhone) || cleanPhone.includes(uPhone);
        });
        if (foundUser) {
          set({ currentUser: foundUser });
          app.showToast(`Welcome back, ${foundUser.name}!`, 'success');
          return { success: true, user: foundUser };
        }

        if (cleanPhone === '9876543210' || cleanPhone === '+919876543210') {
          const u = users.find((x) => x.id === 'u1') || users[0];
          set({ currentUser: u });
          app.showToast(`Logged in as Resident: ${u.name}`, 'success');
          return { success: true, user: u };
        }
        if (cleanPhone === '9999988888' || cleanPhone === '+919999988888') {
          const u = users.find((x) => x.id === 'u2') || users[1];
          set({ currentUser: u });
          app.showToast(`Logged in as Admin: ${u.name}`, 'success');
          return { success: true, user: u };
        }

        return { success: false, message: 'Invalid credentials. Phone number not registered.' };
      },

      logout: () => {
        set({ currentUser: null });
        useAppStore.getState().showToast('Logged out successfully', 'info');
      },
    }),
    {
      name: 'homebandhu-auth',
      storage: createJSONStorage(() => sessionStorage),
    }
  )
);
