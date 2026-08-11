import { COMMUNITY_TYPES, ONBOARDING_CONFIG } from '../data/onboarding.js';

export const createInitialBlock = () => ({ id: 'block-1', name: 'Block A' });

export const createInitialVilla = () => ({ id: 'villa-1', name: 'Villa 1' });

export const createNextBlock = (blocks) => {
  const usedIds = new Set(blocks.map((block) => block.id));
  let sequence = 1;

  while (usedIds.has(`block-${sequence}`)) {
    sequence += 1;
  }

  return {
    id: `block-${sequence}`,
    name: `Block ${String.fromCharCode(64 + sequence)}`,
  };
};

export const createNextVilla = (villas) => {
  const usedIds = new Set(villas.map((villa) => villa.id));
  let sequence = 1;

  while (usedIds.has(`villa-${sequence}`)) {
    sequence += 1;
  }

  return { id: `villa-${sequence}`, name: `Villa ${sequence}` };
};

export const validateAssociationDetails = ({
  associationName,
  addressLine1,
  city,
  state,
  postalCode,
  countryCode,
  latitude,
  longitude,
  communityType,
  blocks,
  villas,
}) => {
  const errors = {};
  const normalizedName = associationName.trim();

  if (!normalizedName) {
    errors.associationName = 'Association name is required.';
  } else if (normalizedName.length < 3) {
    errors.associationName = 'Association name must be at least 3 characters.';
  } else if (normalizedName.length > 100) {
    errors.associationName = 'Association name cannot exceed 100 characters.';
  }

  if (!addressLine1?.trim()) errors.addressLine1 = 'Address line 1 is required.';
  if (!city?.trim()) errors.city = 'City is required.';
  if (!state?.trim()) errors.state = 'State is required.';
  if (!postalCode?.trim()) errors.postalCode = 'Postal code is required.';
  if (!/^[a-z]{2}$/i.test(countryCode?.trim() || '')) {
    errors.countryCode = 'Use a two-letter country code.';
  }
  if (latitude === '' || longitude === '' || !Number.isFinite(Number(latitude)) || !Number.isFinite(Number(longitude))) {
    errors.location = 'Community coordinates are required.';
  }

  if (
    communityType === COMMUNITY_TYPES.APARTMENT &&
    blocks.length < 1
  ) {
    errors.blocks = 'Apartment communities require at least one block.';
  }

  if (
    communityType === COMMUNITY_TYPES.LAYOUT_VILLA &&
    villas.length < 1
  ) {
    errors.villas = 'Layout and Villa communities require at least one villa.';
  }

  return errors;
};

export const canAddBlock = (blocks) =>
  blocks.length < ONBOARDING_CONFIG.MAX_BLOCKS;

export const canAddVilla = (villas) =>
  villas.length < ONBOARDING_CONFIG.MAX_VILLAS;
