import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  server: {
    port: 5173,
    host: '0.0.0.0',
    proxy: {
      '/api': {
        target: process.env.VITE_API_URL || 'http://backend:8000',
        changeOrigin: true,
        ws: true  // Enable WebSocket support for /api routes
      },
      '/ws': {
        target: process.env.VITE_WS_URL || 'ws://backend:8000',
        ws: true
      },
      '/health': {
        target: process.env.VITE_API_URL || 'http://backend:8000',
        changeOrigin: true
      }
    }
  }
})
