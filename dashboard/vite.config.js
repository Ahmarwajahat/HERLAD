import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    watch: {
      ignored: [
        '**/logs/**',
        '**/tasks/**',
        '**/knowledge_base/**',
        '**/reports/**',
        '**/.wwebjs_auth/**'
      ]
    }
  }
})
