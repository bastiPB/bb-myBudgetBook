// ModulesProvider lädt beim Start die systemweiten und persönlichen Einstellungen
// und berechnet daraus die aktiven Module (Zwei-Stufen-Sichtbarkeit, ADR 0008).
// Muss innerhalb von <AuthProvider> eingebettet sein — es verwendet useAuth().
//
// useReducer statt useState: die ESLint-Regel react-hooks/set-state-in-effect verbietet
// synchrone setState-Aufrufe im Effect-Body. dispatch() gilt nicht als "setState"
// und löst die Regel nicht aus — außerdem ist useReducer idiomatisch bei komplexem State.
import { useCallback, useEffect, useReducer, useState } from 'react'
import type { ReactNode } from 'react'

import { fetchProfileSettings } from '../api/profile'
import { fetchSystemSettings } from '../api/settings'
import { MODULE_REGISTRY } from '../modules/registry'
import type { ModuleDefinition } from '../types/module'
import { ModulesContext } from './ModulesContext'
import { useAuth } from './useAuth'

// Alle zusammengehörenden States + loading in einem Reducer-Objekt
interface State {
  activeModules: ModuleDefinition[]
  availableModules: ModuleDefinition[]
  hasChosenModules: boolean
  displayName: string | null
  loading: boolean
}

// Alle möglichen Zustandsübergänge
type Action =
  | { type: 'reset' }    // User ausgeloggt → alles leer
  | { type: 'loading' }  // Fetch gestartet
  | { type: 'loaded'; activeModules: ModuleDefinition[]; availableModules: ModuleDefinition[]; hasChosenModules: boolean; displayName: string | null }
  | { type: 'error' }    // Fetch fehlgeschlagen → sicherer Fallback

// Leerer Zustand (kein User, kein Fetch-Fehler)
const EMPTY: State = {
  activeModules: [],
  availableModules: [],
  hasChosenModules: false,
  displayName: null,
  loading: false,
}

function reducer(state: State, action: Action): State {
  switch (action.type) {
    case 'reset':
      return EMPTY
    case 'loading':
      // Nur loading-Flag setzen — Module bleiben kurz sichtbar während Reload (kein Flicker)
      return { ...state, loading: true }
    case 'loaded':
      return {
        activeModules: action.activeModules,
        availableModules: action.availableModules,
        hasChosenModules: action.hasChosenModules,
        displayName: action.displayName,
        loading: false,
      }
    case 'error':
      return EMPTY
    default:
      return state
  }
}

export function ModulesProvider({ children }: { children: ReactNode }) {
  const { user, loading: authLoading } = useAuth()

  // loading: true beim Start — verhindert kurzes Aufblitzen leerer Navigation
  const [state, dispatch] = useReducer(reducer, { ...EMPTY, loading: true })

  // Zähler der bei reload() hochgezählt wird — löst den useEffect erneut aus
  const [reloadTrigger, setReloadTrigger] = useState(0)

  // reload() kann von SettingsPage und ProfileSettingsPage aufgerufen werden,
  // um Navigation und Onboarding-Card nach Änderungen sofort zu aktualisieren.
  const reload = useCallback(() => setReloadTrigger(prev => prev + 1), [])

  useEffect(() => {
    // Solange AuthProvider noch lädt, nichts tun — der User-Status ist noch unbekannt
    if (authLoading) return

    if (!user) {
      // Kein eingeloggter User → zurücksetzen (dispatch, kein setState — Lint-konform)
      dispatch({ type: 'reset' })
      return
    }

    // Fetch-Phase starten
    dispatch({ type: 'loading' })

    // Beide Endpunkte parallel laden — kein unnötiges Warten (ADR 0008)
    Promise.all([fetchSystemSettings(), fetchProfileSettings()])
      .then(([systemSettings, profileSettings]) => {
        // Stufe 1: Welche Module hat der Admin systemweit freigegeben?
        const adminEnabled = MODULE_REGISTRY.filter(
          m => systemSettings.modules[m.key] === true
        )

        // Stufe 2: Von den Admin-freigegebenen — welche hat der User persönlich aktiviert?
        const userEnabled = adminEnabled.filter(
          m => profileSettings.modules[m.key] === true
        )

        // Onboarding-Flag: hat der User schon irgendein Modul gewählt?
        // Prüft die Roh-Profil-Einstellungen — nicht den gefilterten Stand.
        // So bleibt die Onboarding-Card weg, auch wenn Admin ein Modul temporär sperrt.
        const userHasChosen = Object.values(profileSettings.modules).some(v => v === true)

        dispatch({
          type: 'loaded',
          activeModules: userEnabled,
          availableModules: adminEnabled,
          hasChosenModules: userHasChosen,
          // "" (leerer String aus DB) wird zu null — damit greift der Fallback auf E-Mail
          displayName: profileSettings.display_name || null,
        })
      })
      .catch(() => {
        // Fehler beim Laden → sicherer Fallback: keine Module
        dispatch({ type: 'error' })
      })
  }, [user, authLoading, reloadTrigger])

  return (
    <ModulesContext.Provider value={{
      activeModules: state.activeModules,
      availableModules: state.availableModules,
      hasChosenModules: state.hasChosenModules,
      displayName: state.displayName,
      loading: state.loading,
      reload,
    }}>
      {children}
    </ModulesContext.Provider>
  )
}
