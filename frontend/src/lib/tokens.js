// Opaque single-use invite tokens (the PRD "hash + link").
//
// Opaque = the token carries no data, it's just an unguessable random handle;
// the server (here: the persisted store) is the source of truth for what it
// maps to and whether it's still valid. That's the frontend-only stand-in for a
// real invite system. Backend swap = mint/verify this token server-side (or use
// a signed JWT) — nothing else in the flow changes.

export const createInviteToken = () => {
  const raw =
    globalThis.crypto?.randomUUID?.() ??
    `${Date.now()}-${Math.random().toString(36).slice(2)}`;
  return raw.replace(/-/g, '');
};

export const buildInviteLink = (token) =>
  `${window.location.origin}/join/${token}`;
