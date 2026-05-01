// main.tsx — Einstiegspunkt der App.
// Reihenfolge der Wrapper (von außen nach innen):
//   StrictMode      = React-Entwicklungsmodus: warnt vor häufigen Fehlern
//   BrowserRouter   = aktiviert clientseitiges Routing (URLs ohne Seitenreload)
//   AuthProvider    = stellt den eingeloggten User für die ganze App bereit
//   ModulesProvider = stellt aktive Module bereit (muss NACH AuthProvider kommen, nutzt useAuth)
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'

import { AuthProvider } from './context/AuthProvider'
import { ModulesProvider } from './context/ModulesProvider'
import './index.css'
import App from './App.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <AuthProvider>
        {/* ModulesProvider muss innerhalb AuthProvider sein — es verwendet useAuth() intern */}
        <ModulesProvider>
          <App />
        </ModulesProvider>
      </AuthProvider>
    </BrowserRouter>
  </StrictMode>,
)
