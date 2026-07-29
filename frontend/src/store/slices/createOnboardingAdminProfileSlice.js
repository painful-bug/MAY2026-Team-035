import { ONBOARDING_STEPS } from '../../data/onboarding.js';

const editableProfileFields = new Set([
  'fullName',
  'designation',
  'email',
  'phone',
  'unitNumber',
  'founderStructureId',
]);

export const createEmptyAdminProfile = () => ({
  fullName: '',
  designation: '',
  email: '',
  phone: '',
  unitNumber: '',
  founderStructureId: '',
  profileImage: '',
});

export const normalizeAdminProfile = (profile) => ({
  ...createEmptyAdminProfile(),
  ...(profile ?? {}),
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

  completeAdminProfileStep: () =>
    set((state) => ({
      adminProfile: {
        ...state.adminProfile,
        fullName: state.adminProfile.fullName.trim(),
        email: state.adminProfile.email.trim(),
        unitNumber: state.adminProfile.unitNumber.trim(),
      },
      onboardingStep: ONBOARDING_STEPS.REVIEW,
    })),
});
