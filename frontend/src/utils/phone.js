export const normalizePhoneNumber = (value = '') => {
  const digits = String(value).replace(/\D/g, '');

  if (digits.length === 12 && digits.startsWith('91')) {
    return digits.slice(2);
  }

  return digits;
};

export const sanitizePhoneInput = (value = '') =>
  normalizePhoneNumber(value);

export const isValidMobileNumber = (value = '') =>
  /^\d{10}$/.test(normalizePhoneNumber(value));

export const formatPhoneNumber = (value = '') => {
  const phone = normalizePhoneNumber(value);

  if (!isValidMobileNumber(phone)) {
    return phone;
  }

  return `+91 ${phone.slice(0, 5)} ${phone.slice(5)}`;
};
