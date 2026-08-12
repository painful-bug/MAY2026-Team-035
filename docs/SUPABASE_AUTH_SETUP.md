# Supabase email/password production setup

HomeBandhu keeps Supabase Auth behind the FastAPI same-origin BFF. Complete the
following dashboard configuration before setting `AUTH_CAPTCHA_ENABLED=true` or
enabling email/password in production.

1. In **Authentication → Providers → Email**, enable Email and enable **Confirm
   email**. Set backend `AUTH_EMAIL_CONFIRMATION_REQUIRED=true`; production
   startup rejects `false`. The application flag and Supabase project setting
   must agree. Set the site URL to the deployed frontend origin.
2. In **Authentication → URL Configuration**, add exact redirect URLs:
   `https://app.example.com/auth/confirm-email` and
   `https://app.example.com/auth/reset-password`. Keep the backend OAuth
   callback (`https://api.example.com/api/v1/auth/google/callback`) allowed for
   Google.
3. In **Authentication → Email Templates**, use links that carry the token hash
   to the frontend. Example confirmation URL:
   `https://app.example.com/auth/confirm-email?token_hash={{ .TokenHash }}&type=signup`.
   Recovery uses the same form with `/auth/reset-password` and `type=recovery`.
   HomeBandhu deliberately asks the user to click a button before consuming the
   one-time hash, so mail-security scanners cannot spend it on a GET request.
4. Configure organizational SMTP in **Project Settings → Auth**. The Supabase
   default mail service is not a production delivery channel; disable link
   tracking in the SMTP provider.
5. In **Authentication → CAPTCHA**, select Cloudflare Turnstile and enter the
   Turnstile secret there. Add `VITE_TURNSTILE_SITE_KEY` to the frontend
   environment and set backend `AUTH_CAPTCHA_ENABLED=true`. The browser sends
   the challenge token to the BFF and Supabase validates it; HomeBandhu does
   not implement a separate validator.
6. Enable leaked-password protection and the password/identity security-email
   templates when available. Review Auth rate limits and use custom SMTP.
7. Keep Google OAuth enabled. Google identities and a subsequently added
   password share the same verified Supabase email identity; HomeBandhu RBAC
   still derives exclusively from the active database membership.

Local Supabase explicitly sets `auth.email.enable_confirmations=false`; pair it
with backend `AUTH_EMAIL_CONFIRMATION_REQUIRED=false` only for local/test use.
Production deployment is blocked until a real confirmation email and session
establishment smoke test passes.

The linked hosted project was verified through migration `0047` on 2026-08-11.
Apply later timestamped migrations through the normal forward-only migration
workflow; never modify a migration already recorded in the hosted history.
