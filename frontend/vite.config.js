import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  cacheDir: './.vite-temp-cache',
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/analyze': 'http://localhost:8000',
      '/journal': 'http://localhost:8000',
      '/twilio':  'http://localhost:8000',
      '/caregiver':'http://localhost:8000',
      '/compare': 'http://localhost:8000',
      '/report':  'http://localhost:8000',
    }
  }
})
