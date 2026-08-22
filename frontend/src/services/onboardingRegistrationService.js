import { api } from '../lib/api/client.js';

export const createAssociationRegistration = async ({ onboardingState }) => {
  const result = await api('/onboarding/community', {
    method: 'POST',
    body: JSON.stringify({
      name: onboardingState.associationName,
      community_type: onboardingState.communityType,
      address_line1: onboardingState.addressLine1,
      address_line2: onboardingState.addressLine2 || null,
      city: onboardingState.city,
      state: onboardingState.state,
      postal_code: onboardingState.postalCode,
      country_code: onboardingState.countryCode,
      latitude: Number(onboardingState.latitude),
      longitude: Number(onboardingState.longitude),
      // snake_case like everything else in this one body -- `/onboarding/community`
      // is the API's documented exception to camelCase (API.md §1.3).
      location_label: onboardingState.locationLabel?.trim() || null,
      blocks: onboardingState.blocks,
      villas: onboardingState.villas,
      block_locations: onboardingState.blockLocations,
      villa_locations: onboardingState.villaLocations,
      enabled_features: onboardingState.enabledModules,
      admin_profile: {
        ...onboardingState.adminProfile,
        profileImage: undefined,
      },
    }),
  });
  return { association: result.community, admin: result.admin };
};
