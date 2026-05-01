import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],

  server: {
    proxy: {
      // Alle Anfragen die mit /api beginnen werden an das Backend weitergeleitet.
      // Beispiel: fetch('/api/auth/login') → http://localhost:8888/auth/login
      // Das '/api' wird dabei entfernt (rewrite), weil das Backend keine /api-Prefix kennt.
      // In Produktion macht nginx genau dasselbe.
      '/api': {
        target: 'http://localhost:8888',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
