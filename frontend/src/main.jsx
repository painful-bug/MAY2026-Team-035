import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClientProvider } from '@tanstack/react-query'
import './index.css'
import App from './App.jsx'
import { initCrossTabSync } from './store/sync'
import { queryClient } from './lib/api/queryClient.js'
import { registerServiceWorker } from './lib/push/pushClient.js'

// Start listening for cross-tab state changes (realtime hydration).
initCrossTabSync()

// Registering is not subscribing. This installs public/sw.js so a reload with
// no connectivity still boots the app; a push subscription is a separate,
// permission-gated step the user takes on the profile screen. Failure is
// swallowed inside — a browser without service workers must still get the app.
void registerServiceWorker()

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </StrictMode>,
)
