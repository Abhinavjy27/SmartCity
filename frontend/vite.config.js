import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  optimizeDeps: {
    exclude: ['maplibre-gl'],
  },
  server: {
    port: 3000,
    host: true,
    open: true,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true
      },
      '/health': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true
      },
      '/monitoring': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true
      },
      '/planning': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true
      },
      '/agents': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true
      },
      '/models': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true
      },
      '/alerts': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true
      },
      '/simulations': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true
      },
      '/recommendations': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true
      },
      '/digital-twin': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true
      }
    }
  }
})
