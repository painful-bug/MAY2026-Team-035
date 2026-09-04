// The QR is a transport envelope. Only the secret token identifies a pass at
// the gate; pass ID, guest count, and other embedded metadata are not authority.
export const buildVisitorQrPayload = (pass, secret) => JSON.stringify({
  type: 'homebandhu-visitor-pass',
  version: 2,
  passId: pass.id,
  token: secret.passToken,
  securityCode: secret.securityCode,
  guestCount: pass.guestCount ?? 1,
});

export function visitorCredential(raw) {
  const value = raw.trim();
  if (!value.startsWith('{')) return value;

  let payload;
  try {
    payload = JSON.parse(value);
  } catch {
    throw new Error('This visitor QR is damaged. Ask for a new pass or enter its security code.');
  }
  if (payload.type !== 'homebandhu-visitor-pass' || payload.version !== 2
    || typeof payload.token !== 'string' || !payload.token.trim() || payload.token.length > 200) {
    throw new Error('This is not a supported visitor QR. Ask for a new pass or enter its security code.');
  }
  return payload.token.trim();
}
