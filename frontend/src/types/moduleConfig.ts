// Typen für Modul-Konfigurationen (Slice F).
// Entspricht den Schemas UserModuleConfigRead / UserModuleConfigUpdate im Backend.

// Was das Backend bei GET /profile/module-config zurückgibt
export interface UserModuleConfig {
  subscription_cumulative_calculation: boolean
  subscription_booking_history: boolean
}

// Was bei PATCH /profile/module-config mitgeschickt wird — alle Felder optional
export interface UserModuleConfigUpdate {
  subscription_cumulative_calculation?: boolean
  subscription_booking_history?: boolean
}
