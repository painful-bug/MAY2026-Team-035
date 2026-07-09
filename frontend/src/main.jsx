import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'
import { initCrossTabSync } from './store/sync'

// Start listening for cross-tab state changes (realtime hydration).
initCrossTabSync()

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
