const SECURITY_CODE_MIN = 100000;
const SECURITY_CODE_RANGE = 900000;

const randomSecurityNumber = () => {
  if (globalThis.crypto?.getRandomValues) {
    const values = new Uint32Array(1);
    globalThis.crypto.getRandomValues(values);
    return SECURITY_CODE_MIN + (values[0] % SECURITY_CODE_RANGE);
  }

  return SECURITY_CODE_MIN + Math.floor(Math.random() * SECURITY_CODE_RANGE);
};

export const getVisitorSecurityCode = (visitor) =>
  visitor?.securityCode || visitor?.code || '';

export const generateVisitorSecurityCode = (visitors = []) => {
  const usedCodes = new Set(visitors.map(getVisitorSecurityCode).filter(Boolean));
  let securityCode = '';

  do {
    securityCode = String(randomSecurityNumber());
  } while (usedCodes.has(securityCode));

  return securityCode;
};
