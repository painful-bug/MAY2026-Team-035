import { registeredAdmins } from '../data/admins.js';
import { normalizePhoneNumber } from '../utils/phone.js';

// This async boundary intentionally mirrors the future API contract. Replacing
// its body with an Axios request will not require changes in the store or pages.
export const findRegisteredAdmin = async (phone) => {
  const normalizedPhone = normalizePhoneNumber(phone);

  return (
    registeredAdmins.find(
      (admin) => normalizePhoneNumber(admin.phone) === normalizedPhone
    ) ?? null
  );
};

// Frontend-only OTP verification contract. The OTP is intentionally ignored in
// this milestone; a future Axios implementation can consume the same payload.
export const verifyAdminOtp = async ({ phone }) => {
  const admin = await findRegisteredAdmin(phone);

  if (!admin) {
    return {
      success: false,
      message: 'This mobile number is not registered as an administrator.',
    };
  }

  return { success: true, admin };
};
