import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClientProvider } from '@tanstack/react-query'
import './index.css'
import App from './App.jsx'
import { initCrossTabSync } from './store/sync'
import { queryClient } from './lib/api/queryClient.js'

// Start listening for cross-tab state changes (realtime hydration).
initCrossTabSync()

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </StrictMode>,
)
