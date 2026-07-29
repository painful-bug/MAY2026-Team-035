import { createAssociationRegistration } from '../../services/onboardingRegistrationService.js';

export const ASSOCIATION_CREATION_STATUS = Object.freeze({
  IDLE: 'idle',
  CREATING: 'creating',
  SUCCESS: 'success',
  ERROR: 'error',
});

export const createInitialCompletionState = () => ({
  associationCreationStatus: ASSOCIATION_CREATION_STATUS.IDLE,
  createdAssociation: null,
  createdAdmin: null,
});

export const createOnboardingCompletionSlice = (set, get) => ({
  ...createInitialCompletionState(),

  createAssociation: async () => {
    set({ associationCreationStatus: ASSOCIATION_CREATION_STATUS.CREATING });

    try {
      const result = await createAssociationRegistration({
        onboardingState: get(),
      });
      set({
        associationCreationStatus: ASSOCIATION_CREATION_STATUS.SUCCESS,
        createdAssociation: result.association,
        createdAdmin: result.admin,
      });
      return { success: true, ...result };
    } catch {
      set({ associationCreationStatus: ASSOCIATION_CREATION_STATUS.ERROR });
      return {
        success: false,
        message: 'Unable to create the association. Please try again.',
      };
    }
  },
});
