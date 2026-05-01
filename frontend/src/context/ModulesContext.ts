import { createContext } from 'react'

import type { ModuleDefinition } from '../types/module'

export interface ModulesContextType {
  // Module die sowohl Admin als auch User aktiviert haben — erscheinen in Navigation + Routing (Stufe 1 + 2)
  activeModules: ModuleDefinition[]
  // Module die der Admin systemweit freigegeben hat — wird auf /profile/settings zur Auswahl angezeigt (nur Stufe 1)
  availableModules: ModuleDefinition[]
  // true wenn der User mindestens ein Modul in seinem Profil aktiviert hat
  // false → Dashboard zeigt Onboarding-Card
  hasChosenModules: boolean
  // Anzeigename aus user_settings — null wenn noch nicht gesetzt (Fallback: E-Mail-Präfix)
  displayName: string | null
  loading: boolean
  // Neu laden — nach Änderungen in SettingsPage oder ProfileSettingsPage aufrufen
  reload: () => void
}

export const ModulesContext = createContext<ModulesContextType | null>(null)
