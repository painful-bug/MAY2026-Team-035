# Implemented flows

1. `/api/v1/auth/google/start` creates a five-minute, signed PKCE transaction
   and redirects to Google through Supabase Auth.
2. `/api/v1/auth/google/callback` validates state, exchanges the code server
   side, establishes HTTP-only access/refresh cookies, and returns to a clean
   frontend path.
3. `/api/v1/auth/session`, `/refresh`, and `/logout` expose only safe session
   context and never provider credentials.
4. `/join/:token` or `/join` prepares an opaque invitation; redemption creates
   membership only when the signed-in Google email exactly matches the invite.
5. An authenticated Google identity without membership can complete founder
   onboarding; database creation is delegated to one atomic SQL function.
