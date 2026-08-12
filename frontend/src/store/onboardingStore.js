import { create } from 'zustand';
import { createJSONStorage, persist } from 'zustand/middleware';
import {
  COMMUNITY_TYPES,
  ONBOARDING_CONFIG,
  ONBOARDING_STEPS,
} from '../data/onboarding.js';
import {
  createInitialBlock,
  createInitialVilla,
  createNextBlock,
  createNextVilla,
} from '../utils/onboarding.js';
import {
  createInitialFeaturesState,
  createOnboardingFeaturesSlice,
  sanitizeEnabledModules,
} from './slices/createOnboardingFeaturesSlice.js';
import {
  createInitialAdminProfileState,
  createOnboardingAdminProfileSlice,
  normalizeAdminProfile,
} from './slices/createOnboardingAdminProfileSlice.js';
import {
  createInitialCompletionState,
  createOnboardingCompletionSlice,
} from './slices/createOnboardingCompletionSlice.js';

const createInitialOnboardingState = () => ({
  associationName: '',
  addressLine1: '',
  addressLine2: '',
  city: '',
  state: '',
  postalCode: '',
  countryCode: 'IN',
  latitude: '',
  longitude: '',
  communityType: COMMUNITY_TYPES.APARTMENT,
  blocks: [createInitialBlock()],
  villas: [createInitialVilla()],
  onboardingStep: ONBOARDING_STEPS.ASSOCIATION_DETAILS,
  blockLocations: {},
  villaLocations: {},
  currentSelectedBlock: null,
  currentSelectedVilla: null,
  ...createInitialFeaturesState(),
  ...createInitialAdminProfileState(),
  ...createInitialCompletionState(),
});

const withoutLocation = (locations, entityId) =>
  Object.fromEntries(
    Object.entries(locations).filter(
      ([locationEntityId]) => locationEntityId !== entityId
    )
  );

const findFirstUnconfigured = (entities, locations) =>
  entities.find((entity) => !locations[entity.id])?.id ?? null;

export const useOnboardingStore = create(
  persist(
    (set, get) => ({
      ...createInitialOnboardingState(),
      ...createOnboardingFeaturesSlice(set),
      ...createOnboardingAdminProfileSlice(set),
      ...createOnboardingCompletionSlice(set, get),

      setAssociationName: (associationName) => set({ associationName }),
      setAddressField: (field, value) => {
        const fields = {
          addressLine1: 'addressLine1', addressLine2: 'addressLine2', city: 'city',
          state: 'state', postalCode: 'postalCode', countryCode: 'countryCode',
        };
        if (fields[field]) set({ [fields[field]]: value });
      },
      setCommunityCoordinates: ({ latitude, longitude }) => set({ latitude, longitude }),

      setCommunityType: (communityType) =>
        set((state) => ({
          communityType,
          blocks:
            communityType === COMMUNITY_TYPES.APARTMENT &&
            state.blocks.length === 0
              ? [createInitialBlock()]
              : state.blocks,
          villas:
            communityType === COMMUNITY_TYPES.LAYOUT_VILLA &&
            state.villas.length === 0
              ? [createInitialVilla()]
              : state.villas,
          currentSelectedBlock:
            communityType === COMMUNITY_TYPES.APARTMENT
              ? state.currentSelectedBlock
              : null,
          currentSelectedVilla:
            communityType === COMMUNITY_TYPES.LAYOUT_VILLA
              ? state.currentSelectedVilla
              : null,
        })),

      updateBlock: (blockId, name) =>
        set((state) => ({
          blocks: state.blocks.map((block) =>
            block.id === blockId ? { ...block, name } : block
          ),
        })),

      addBlock: () =>
        set((state) =>
          state.blocks.length >= ONBOARDING_CONFIG.MAX_BLOCKS
            ? state
            : { blocks: [...state.blocks, createNextBlock(state.blocks)] }
        ),

      removeBlock: (blockId) =>
        set((state) => {
          if (state.blocks.length <= 1) {
            return state;
          }

          const blocks = state.blocks.filter((block) => block.id !== blockId);
          const blockLocations = withoutLocation(
            state.blockLocations,
            blockId
          );
          const currentSelectedBlock =
            state.currentSelectedBlock === blockId
              ? findFirstUnconfigured(blocks, blockLocations)
              : state.currentSelectedBlock;

          return { blocks, blockLocations, currentSelectedBlock };
        }),

      updateVilla: (villaId, name) =>
        set((state) => ({
          villas: state.villas.map((villa) =>
            villa.id === villaId ? { ...villa, name } : villa
          ),
        })),

      addVilla: () =>
        set((state) =>
          state.villas.length >= ONBOARDING_CONFIG.MAX_VILLAS
            ? state
            : { villas: [...state.villas, createNextVilla(state.villas)] }
        ),

      removeVilla: (villaId) =>
        set((state) => {
          if (state.villas.length <= 1) {
            return state;
          }

          const villas = state.villas.filter((villa) => villa.id !== villaId);
          const villaLocations = withoutLocation(
            state.villaLocations,
            villaId
          );
          const currentSelectedVilla =
            state.currentSelectedVilla === villaId
              ? findFirstUnconfigured(villas, villaLocations)
              : state.currentSelectedVilla;

          return { villas, villaLocations, currentSelectedVilla };
        }),

      setOnboardingStep: (onboardingStep) => set({ onboardingStep }),

      completeAssociationStep: () =>
        set((state) => ({
          associationName: state.associationName.trim(),
          addressLine1: state.addressLine1.trim(),
          addressLine2: state.addressLine2.trim(),
          city: state.city.trim(),
          state: state.state.trim(),
          postalCode: state.postalCode.trim(),
          countryCode: state.countryCode.trim().toUpperCase(),
          onboardingStep: ONBOARDING_STEPS.MAP_CONFIGURATION,
          currentSelectedBlock:
            state.communityType === COMMUNITY_TYPES.APARTMENT
              ? findFirstUnconfigured(state.blocks, state.blockLocations)
              : null,
          currentSelectedVilla:
            state.communityType === COMMUNITY_TYPES.LAYOUT_VILLA
              ? findFirstUnconfigured(state.villas, state.villaLocations)
              : null,
        })),

      initializeMapSelection: () =>
        set((state) => {
          if (state.communityType === COMMUNITY_TYPES.APARTMENT) {
            return state.currentSelectedBlock
              ? state
              : {
                  currentSelectedBlock: findFirstUnconfigured(
                    state.blocks,
                    state.blockLocations
                  ),
                };
          }

          return state.currentSelectedVilla
            ? state
            : {
                currentSelectedVilla: findFirstUnconfigured(
                  state.villas,
                  state.villaLocations
                ),
              };
        }),

      selectBlock: (blockId) =>
        set((state) => ({
          currentSelectedBlock:
            state.communityType === COMMUNITY_TYPES.APARTMENT &&
            state.blocks.some((block) => block.id === blockId)
              ? blockId
              : state.currentSelectedBlock,
        })),

      selectVilla: (villaId) =>
        set((state) => ({
          currentSelectedVilla:
            state.communityType === COMMUNITY_TYPES.LAYOUT_VILLA &&
            state.villas.some((villa) => villa.id === villaId)
              ? villaId
              : state.currentSelectedVilla,
        })),

      setSelectedBlockLocation: (coordinates) =>
        set((state) => {
          if (
            state.communityType !== COMMUNITY_TYPES.APARTMENT ||
            !state.currentSelectedBlock
          ) {
            return state;
          }

          const blockLocations = {
            ...state.blockLocations,
            [state.currentSelectedBlock]: coordinates,
          };

          return {
            blockLocations,
            currentSelectedBlock: findFirstUnconfigured(
              state.blocks,
              blockLocations
            ),
          };
        }),

      setSelectedVillaLocation: (coordinates) =>
        set((state) => {
          if (
            state.communityType !== COMMUNITY_TYPES.LAYOUT_VILLA ||
            !state.currentSelectedVilla
          ) {
            return state;
          }

          const villaLocations = {
            ...state.villaLocations,
            [state.currentSelectedVilla]: coordinates,
          };

          return {
            villaLocations,
            currentSelectedVilla: findFirstUnconfigured(
              state.villas,
              villaLocations
            ),
          };
        }),

      completeMapStep: () => {
        let completed = false;

        set((state) => {
          const apartmentComplete =
            state.communityType === COMMUNITY_TYPES.APARTMENT &&
            state.blocks.every((block) => state.blockLocations[block.id]);
          const villaComplete =
            state.communityType === COMMUNITY_TYPES.LAYOUT_VILLA &&
            state.villas.every((villa) => state.villaLocations[villa.id]);

          completed = apartmentComplete || villaComplete;

          return completed
            ? { onboardingStep: ONBOARDING_STEPS.FEATURE_CONFIGURATION }
            : state;
        });

        return completed;
      },

      resetOnboarding: () => set(createInitialOnboardingState()),
    }),
    {
      name: 'homebandhu-admin-onboarding',
      storage: createJSONStorage(() => sessionStorage),
      version: 7,
      migrate: (persistedState) => {
        const {
          boundaryCoordinates: _boundaryCoordinates,
          ...currentState
        } = persistedState;

        return {
          ...currentState,
          addressLine1: currentState.addressLine1 ?? '',
          addressLine2: currentState.addressLine2 ?? '',
          city: currentState.city ?? '',
          state: currentState.state ?? '',
          postalCode: currentState.postalCode ?? '',
          countryCode: currentState.countryCode ?? 'IN',
          latitude: currentState.latitude ?? '',
          longitude: currentState.longitude ?? '',
          villas:
            currentState.villas?.length > 0
              ? currentState.villas
              : [createInitialVilla()],
          villaLocations: currentState.villaLocations ?? {},
          currentSelectedVilla: currentState.currentSelectedVilla ?? null,
          enabledModules: sanitizeEnabledModules(currentState.enabledModules),
          adminProfile: normalizeAdminProfile(currentState.adminProfile),
          ...createInitialCompletionState(),
        };
      },
    }
  )
);
