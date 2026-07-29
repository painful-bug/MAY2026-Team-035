# React + Vite

This template provides a minimal setup to get React working in Vite with HMR and some Oxlint rules.

## Supabase authentication

Copy `.env.example` to `.env.local` and set the public Supabase URL and
publishable key. Google is the default primary provider and SMS OTP is the
secondary provider; swap `VITE_AUTH_PRIMARY_PROVIDER` and
`VITE_AUTH_SECONDARY_PROVIDER` (`google` / `otp`) to reverse that order without
changing application code.

In Supabase, enable Google under **Authentication → Providers**, add
`http://localhost:5173/auth/callback` (and the production equivalent) to the
redirect allow list, and enable manual identity linking. Existing phone users
can sign in once with OTP and choose **Link Google sign-in** in their profile.
Supabase automatically links matching verified email identities where available.

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react) uses [Oxc](https://oxc.rs)
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react-swc) uses [SWC](https://swc.rs/)

## React Compiler

The React Compiler is not enabled on this template because of its impact on dev & build performances. To add it, see [this documentation](https://react.dev/learn/react-compiler/installation).

## Expanding the Oxlint configuration

If you are developing a production application, we recommend using TypeScript with type-aware lint rules enabled. Check out the [TS template](https://github.com/vitejs/vite/tree/main/packages/create-vite/template-react-ts) for information on how to integrate TypeScript and Oxlint's TypeScript related rules in your project.
