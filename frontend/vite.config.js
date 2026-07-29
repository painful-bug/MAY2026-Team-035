import { defineConfig, loadEnv } from 'vite'
import path from 'node:path'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const frontendEnv = loadEnv(mode, process.cwd(), '')
  const backendEnv = loadEnv(mode, path.resolve(process.cwd(), '../backend'), '')

  // Local development already keeps Supabase credentials in backend/.env. The
  // anon key is intentionally public, so use it only as a development fallback
  // when dedicated VITE_* values have not been supplied. Service-role values
  // are never read or exposed to the client.
  const supabaseUrl = frontendEnv.VITE_SUPABASE_URL || backendEnv.SUPABASE_URL || ''
  const supabasePublishableKey =
    frontendEnv.VITE_SUPABASE_PUBLISHABLE_KEY || backendEnv.SUPABASE_ANON_KEY || ''

  return {
    plugins: [
      react(),
      tailwindcss(),
    ],
    define: {
      'import.meta.env.VITE_SUPABASE_URL': JSON.stringify(supabaseUrl),
      'import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY': JSON.stringify(supabasePublishableKey),
    },
  }
})
