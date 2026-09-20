import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react()],
  // ketcher-react reads process.env at runtime.
  define: {
    'process.env': {},
    global: 'globalThis',
  },
  server: {
    proxy: { '/api': 'http://127.0.0.1:8000' },
  },
})
