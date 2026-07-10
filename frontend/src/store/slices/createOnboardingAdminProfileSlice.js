import { ONBOARDING_STEPS } from '../../data/onboarding.js';
import { normalizePhoneNumber } from '../../utils/phone.js';

const editableProfileFields = new Set([
  'fullName',
  'designation',
  'email',
  'unitNumber',
]);

export const createEmptyAdminProfile = () => ({
  fullName: '',
  designation: '',
  email: '',
  phone: '',
  unitNumber: '',
  profileImage: '',
});

export const normalizeAdminProfile = (profile) => ({
  ...createEmptyAdminProfile(),
  ...(profile ?? {}),
  phone: normalizePhoneNumber(profile?.phone),
});

export const createInitialAdminProfileState = () => ({
  adminProfile: createEmptyAdminProfile(),
});

export const createOnboardingAdminProfileSlice = (set) => ({
  ...createInitialAdminProfileState(),

  setAdminProfileField: (field, value) =>
    set((state) => {
      if (!editableProfileFields.has(field)) {
        return state;
      }

      return { adminProfile: { ...state.adminProfile, [field]: value } };
    }),

  setAdminProfileImage: (profileImage) =>
    set((state) => ({
      adminProfile: { ...state.adminProfile, profileImage },
    })),

  setAdminProfile: (profile) =>
    set({ adminProfile: normalizeAdminProfile(profile) }),

  syncAdminProfilePhone: (phone) =>
    set((state) => {
      const normalizedPhone = normalizePhoneNumber(phone);

      if (!normalizedPhone || state.adminProfile.phone === normalizedPhone) {
        return state;
      }

      return {
        adminProfile: { ...state.adminProfile, phone: normalizedPhone },
      };
    }),

  completeAdminProfileStep: () =>
    set((state) => ({
      adminProfile: {
        ...state.adminProfile,
        fullName: state.adminProfile.fullName.trim(),
        email: state.adminProfile.email.trim(),
        unitNumber: state.adminProfile.unitNumber.trim(),
      },
      onboardingStep: ONBOARDING_STEPS.ONBOARDING_OTP,
    })),
});
