// Beschreibt ein einzelnes Modul wie es im Frontend bekannt ist.
// Die DB speichert nur true/false — diese Beschreibung (Label, Route, ...) lebt im Code.
export interface ModuleDefinition {
  // Eindeutiger Key — muss exakt mit dem DB-Key übereinstimmen (z.B. "savings_box")
  key: string
  // Anzeigename auf der Settings-Seite (z.B. "Sparfach")
  label: string
  // Kurzbeschreibung für die Settings-Seite
  description: string
  // URL-Pfad der Modul-Seite (z.B. "/savings-box")
  route: string
  // Kurzform für den Navigations-Menüeintrag (z.B. "Sparfach")
  navLabel: string
}
