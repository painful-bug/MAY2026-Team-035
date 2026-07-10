import { COMMUNITY_TYPES } from '../data/onboarding.js';
import { genId } from '../lib/ids.js';

// Frontend-only registration boundary. A future implementation can replace
// this function with verify-OTP and register-association API calls.
export const createAssociationRegistration = async ({
  otp: _otp,
  onboardingState,
}) => {
  const {
    associationName,
    communityType,
    blocks,
    villas,
    blockLocations,
    villaLocations,
    enabledModules,
    adminProfile,
  } = onboardingState;
  const associationId = genId('association');
  const apartmentMode = communityType === COMMUNITY_TYPES.APARTMENT;
  const units = apartmentMode ? blocks : villas;
  const unitLocations = apartmentMode ? blockLocations : villaLocations;

  const association = {
    id: associationId,
    name: associationName,
    communityType,
    unitType: apartmentMode ? 'Blocks' : 'Villas',
    unitCount: units.length,
    units: units.map((unit) => ({
      ...unit,
      coordinates: unitLocations[unit.id] ?? null,
    })),
    enabledModules: [...enabledModules],
    status: 'Active',
  };

  const admin = {
    id: genId('admin'),
    name: adminProfile.fullName,
    fullName: adminProfile.fullName,
    designation: adminProfile.designation,
    email: adminProfile.email,
    phone: adminProfile.phone,
    role: 'Admin',
    tower: apartmentMode ? adminProfile.unitNumber.split('-')[0] : '',
    flat: adminProfile.unitNumber,
    unitNumber: adminProfile.unitNumber,
    apartmentId: adminProfile.unitNumber,
    profileImage: adminProfile.profileImage,
    associationId,
    status: 'Active',
  };

  return { association, admin };
};
