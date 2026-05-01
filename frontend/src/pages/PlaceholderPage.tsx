// Wiederverwendbare Platzhalter-Seite für Module die noch in Entwicklung sind.
// Wird für alle Module außer dem Abo-Manager verwendet (v0.2.0).
// In späteren Versionen wird diese Seite durch die echte Modul-Seite ersetzt.

interface Props {
  moduleName: string
}

export default function PlaceholderPage({ moduleName }: Props) {
  return (
    <div style={{ padding: '2rem', textAlign: 'center' }}>
      <h1>{moduleName}</h1>
      <p style={{ color: '#666', marginTop: '1rem' }}>
        Dieses Modul ist in Entwicklung und wird in einer zukünftigen Version verfügbar sein.
      </p>
    </div>
  )
}
