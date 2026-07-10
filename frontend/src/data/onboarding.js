export const COMMUNITY_TYPES = Object.freeze({
  APARTMENT: 'apartment',
  LAYOUT_VILLA: 'layout_villa',
});

export const communityTypeOptions = Object.freeze([
  { value: COMMUNITY_TYPES.APARTMENT, label: 'Apartment' },
  { value: COMMUNITY_TYPES.LAYOUT_VILLA, label: 'Layout / Villa' },
]);

export const ONBOARDING_CONFIG = Object.freeze({
  TOTAL_STEPS: 5,
  MAX_BLOCKS: 10,
  MAX_VILLAS: 50,
});

export const ONBOARDING_STEPS = Object.freeze({
  ASSOCIATION_DETAILS: 1,
  MAP_CONFIGURATION: 2,
  FEATURE_CONFIGURATION: 3,
  ADMIN_PROFILE: 4,
  ONBOARDING_OTP: 5,
});
