import { ONBOARDING_STEPS } from '../../data/onboarding.js';
import {
  defaultEnabledModules,
  onboardingModules,
} from '../../data/onboardingModules.js';

const validModuleIds = new Set(onboardingModules.map((module) => module.id));

export const createInitialFeaturesState = () => ({
  enabledModules: [...defaultEnabledModules],
});

export const sanitizeEnabledModules = (moduleIds) => {
  if (!Array.isArray(moduleIds)) {
    return [...defaultEnabledModules];
  }

  return [
    ...new Set(moduleIds.filter((moduleId) => validModuleIds.has(moduleId))),
  ];
};

export const createOnboardingFeaturesSlice = (set) => ({
  ...createInitialFeaturesState(),

  toggleModule: (moduleId) =>
    set((state) => {
      if (!validModuleIds.has(moduleId)) {
        return state;
      }

      return {
        enabledModules: state.enabledModules.includes(moduleId)
          ? state.enabledModules.filter((enabledId) => enabledId !== moduleId)
          : [...state.enabledModules, moduleId],
      };
    }),

  setEnabledModules: (moduleIds) =>
    set({ enabledModules: sanitizeEnabledModules(moduleIds) }),

  completeFeatureStep: () =>
    set({ onboardingStep: ONBOARDING_STEPS.ADMIN_PROFILE }),
});
