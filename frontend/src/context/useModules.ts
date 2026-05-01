import { useContext } from 'react'

import { ModulesContext } from './ModulesContext'

export function useModules() {
  const ctx = useContext(ModulesContext)
  if (!ctx) throw new Error('useModules() muss innerhalb von <ModulesProvider> verwendet werden')
  return ctx
}
