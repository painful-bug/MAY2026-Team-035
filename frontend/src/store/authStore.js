import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import { useAppStore } from './appStore';
import { demoAuthAccounts } from '../data/authentication';
import {
  findRegisteredAdmin,
  verifyAdminOtp,
} from '../services/adminAuthService';
import {
  isValidMobileNumber,
  normalizePhoneNumber,
  sanitizePhoneInput,
} from '../utils/phone';

export const ADMIN_REGISTRATION_STATUS = Object.freeze({
  UNKNOWN: 'unknown',
  REGISTERED: 'registered',
  NEW_ADMIN: 'new_admin',
});

export const AUTH_FLOW_STATE = Object.freeze({
  IDLE: 'idle',
  CHECKING_REGISTRATION: 'checking_registration',
  OTP_REQUIRED: 'otp_required',
  OTP_SUBMITTING: 'otp_submitting',
  REGISTRATION_REQUIRED: 'registration_required',
  AUTHENTICATED: 'authenticated',
});

const initialAdminAuthState = {
  currentPhone: '',
  registrationStatus: ADMIN_REGISTRATION_STATUS.UNKNOWN,
  authFlowState: AUTH_FLOW_STATE.IDLE,
  pendingAdmin: null,
};

// Auth is scoped per-tab on purpose: currentUser persists to sessionStorage, so
// a resident tab and an admin tab stay independently logged in (both reading the
// same shared domain data from useAppStore). login/logout reach into the app
// store at call time (not import time) — the circular import is safe because
// nothing crosses stores during module evaluation.
export const useAuthStore = create(
  persist(
    (set, get) => ({
      currentUser: null,
      ...initialAdminAuthState,

      setCurrentUser: (currentUser) =>
        set({
          currentUser,
          authFlowState: currentUser
            ? AUTH_FLOW_STATE.AUTHENTICATED
            : AUTH_FLOW_STATE.IDLE,
        }),

      setCurrentPhone: (phone) =>
        set({
          currentPhone: sanitizePhoneInput(phone),
          registrationStatus: ADMIN_REGISTRATION_STATUS.UNKNOWN,
          authFlowState: AUTH_FLOW_STATE.IDLE,
          pendingAdmin: null,
        }),

      startAdminAuthentication: async () => {
        const phone = normalizePhoneNumber(get().currentPhone);

        if (!isValidMobileNumber(phone)) {
          return {
            success: false,
            message: 'Please enter a valid 10-digit mobile number.',
          };
        }

        set({
          currentUser: null,
          authFlowState: AUTH_FLOW_STATE.CHECKING_REGISTRATION,
        });

        try {
          const admin = await findRegisteredAdmin(phone);

          if (admin) {
            set({
              currentPhone: phone,
              registrationStatus: ADMIN_REGISTRATION_STATUS.REGISTERED,
              authFlowState: AUTH_FLOW_STATE.OTP_REQUIRED,
              pendingAdmin: admin,
            });
            return { success: true, isRegistered: true };
          }

          set({
            currentPhone: phone,
            registrationStatus: ADMIN_REGISTRATION_STATUS.NEW_ADMIN,
            authFlowState: AUTH_FLOW_STATE.REGISTRATION_REQUIRED,
            pendingAdmin: null,
          });
          return { success: true, isRegistered: false };
        } catch {
          set({ authFlowState: AUTH_FLOW_STATE.IDLE });
          return {
            success: false,
            message: 'Unable to check admin registration. Please try again.',
          };
        }
      },

      // Task 1 fix: model submission and authentication as separate states.
      // The mock service accepts every OTP; its async contract matches the
      // future verify-OTP API boundary.
      submitAdminOtp: async (otp) => {
        const { currentPhone, registrationStatus, authFlowState } = get();

        if (
          registrationStatus !== ADMIN_REGISTRATION_STATUS.REGISTERED ||
          authFlowState !== AUTH_FLOW_STATE.OTP_REQUIRED
        ) {
          return {
            success: false,
            message: 'Start the admin login flow before submitting an OTP.',
          };
        }

        set({ authFlowState: AUTH_FLOW_STATE.OTP_SUBMITTING });

        try {
          const result = await verifyAdminOtp({ phone: currentPhone, otp });

          if (!result.success) {
            set({ authFlowState: AUTH_FLOW_STATE.OTP_REQUIRED });
            return result;
          }

          set({
            currentUser: result.admin,
            authFlowState: AUTH_FLOW_STATE.AUTHENTICATED,
            pendingAdmin: null,
          });
          useAppStore
            .getState()
            .showToast(`Welcome back, ${result.admin.name}!`, 'success');
          return { success: true, user: result.admin };
        } catch {
          set({ authFlowState: AUTH_FLOW_STATE.OTP_REQUIRED });
          return {
            success: false,
            message: 'Unable to submit the OTP. Please try again.',
          };
        }
      },

      resetAdminAuthentication: () =>
        set({ currentUser: null, ...initialAdminAuthState }),

      // Temporary direct login used only by the Resident/Admin demonstration
      // shortcut buttons retained until the Resident Portal is replaced.
      login: (phone) => {
        const app = useAppStore.getState();
        const users = app.users;
        const cleanPhone = normalizePhoneNumber(phone);

        const foundUser = users.find((u) => {
          const userPhone = normalizePhoneNumber(u.phone);
          return userPhone === cleanPhone;
        });
        const securityDepartment = app.departments.find((department) => {
          const handlesSecurity =
            department.name.toLowerCase().includes('security') ||
            department.categories?.some(
              (category) => category.toLowerCase() === 'security'
            );
          return (
            department.status !== 'Inactive' &&
            handlesSecurity &&
            department.staff?.some(
              (member) =>
                normalizePhoneNumber(member.phone) === cleanPhone
            )
          );
        });
        const securityStaff = securityDepartment?.staff.find(
          (member) => normalizePhoneNumber(member.phone) === cleanPhone
        );
        const securityUser = securityStaff
          ? {
              id: `security-${securityStaff.id}`,
              name: securityStaff.name,
              phone: securityStaff.phone,
              role: 'Security',
              staffRole: securityStaff.role,
              departmentId: securityDepartment.id,
              departmentName: securityDepartment.name,
              status: 'Active',
              tower: 'Community',
              flat: 'Main Gate',
            }
          : null;
        const communityUser = foundUser || securityUser;

        if (communityUser) {
          set({
            currentUser: communityUser,
            currentPhone: cleanPhone,
            registrationStatus:
              communityUser.role === 'Admin'
                ? ADMIN_REGISTRATION_STATUS.REGISTERED
                : ADMIN_REGISTRATION_STATUS.UNKNOWN,
            authFlowState: AUTH_FLOW_STATE.AUTHENTICATED,
            pendingAdmin: null,
          });
          app.showToast(`Welcome back, ${communityUser.name}!`, 'success');
          return { success: true, user: communityUser };
        }

        const demoAccount = demoAuthAccounts.find(
          (account) => normalizePhoneNumber(account.phone) === cleanPhone
        );

        if (demoAccount) {
          const u =
            users.find((user) => user.id === demoAccount.userId) ||
            users.find((user) => user.role === demoAccount.role);

          if (!u) {
            return { success: false, message: 'Demo account is unavailable.' };
          }

          set({
            currentUser: u,
            currentPhone: cleanPhone,
            registrationStatus:
              demoAccount.role === 'Admin'
                ? ADMIN_REGISTRATION_STATUS.REGISTERED
                : ADMIN_REGISTRATION_STATUS.UNKNOWN,
            authFlowState: AUTH_FLOW_STATE.AUTHENTICATED,
            pendingAdmin: null,
          });
          app.showToast(`Logged in as ${demoAccount.role}: ${u.name}`, 'success');
          return { success: true, user: u };
        }

        return { success: false, message: 'Invalid credentials. Phone number not registered.' };
      },

      logout: () => {
        set({ currentUser: null, ...initialAdminAuthState });
        useAppStore.getState().showToast('Logged out successfully', 'info');
      },
    }),
    {
      name: 'homebandhu-auth',
      storage: createJSONStorage(() => sessionStorage),
    }
  )
);
