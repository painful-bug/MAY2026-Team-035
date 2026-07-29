export const AUTH_PROVIDER = Object.freeze({
  GOOGLE: 'google',
  OTP: 'otp',
});

const supportedProviders = new Set(Object.values(AUTH_PROVIDER));

function configuredProvider(value, fallback) {
  const provider = String(value || fallback).trim().toLowerCase();
  return supportedProviders.has(provider) ? provider : fallback;
}

// These two variables are the only switch needed to change which sign-in
// method leads the UI. Keep both methods enabled in Supabase when using one as
// a fallback.
export const authConfiguration = Object.freeze({
  primaryProvider: configuredProvider(
    import.meta.env.VITE_AUTH_PRIMARY_PROVIDER,
    AUTH_PROVIDER.GOOGLE
  ),
  secondaryProvider: configuredProvider(
    import.meta.env.VITE_AUTH_SECONDARY_PROVIDER,
    AUTH_PROVIDER.OTP
  ),
});

export function availableAuthProviders() {
  return [...new Set([
    authConfiguration.primaryProvider,
    authConfiguration.secondaryProvider,
  ])];
}

export const providerLabels = Object.freeze({
  [AUTH_PROVIDER.GOOGLE]: 'Continue with Google',
  [AUTH_PROVIDER.OTP]: 'Use phone OTP',
});
