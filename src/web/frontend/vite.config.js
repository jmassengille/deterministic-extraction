import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
  ],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        // SSE requires special handling
        configure: (proxy, options) => {
          proxy.on('proxyReq', (proxyReq, req, res) => {
            if (req.url.includes('/progress')) {
              proxyReq.setHeader('Connection', 'keep-alive')
              proxyReq.setHeader('Accept', 'text/event-stream')
            }
          })
          proxy.on('proxyRes', (proxyRes, req, res) => {
            if (req.url.includes('/progress')) {
              // Disable buffering for SSE
              proxyRes.headers['x-accel-buffering'] = 'no'
              proxyRes.headers['cache-control'] = 'no-cache'
              proxyRes.headers['connection'] = 'keep-alive'
            }
          })
        },
        timeout: 0,  // No timeout for SSE
        proxyTimeout: 0,
        ws: false  // Disable WebSocket upgrade for SSE
      }
    }
  }
})