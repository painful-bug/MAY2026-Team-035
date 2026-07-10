const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export const validateAdminProfile = ({ fullName, email, unitNumber }) => {
  const errors = {};
  const normalizedName = fullName.trim();

  if (!normalizedName) {
    errors.fullName = 'Full name is required.';
  } else if (normalizedName.length < 3) {
    errors.fullName = 'Full name must be at least 3 characters.';
  }

  if (!email.trim()) {
    errors.email = 'Email address is required.';
  } else if (!EMAIL_PATTERN.test(email.trim())) {
    errors.email = 'Enter a valid email address.';
  }

  if (!unitNumber.trim()) {
    errors.unitNumber = 'Residence number is required.';
  }

  return errors;
};

export const getProfileInitials = (fullName) => {
  const names = fullName.trim().split(/\s+/).filter(Boolean);

  if (names.length === 0) {
    return 'AD';
  }

  return names
    .slice(0, 2)
    .map((name) => name.charAt(0).toUpperCase())
    .join('');
};
