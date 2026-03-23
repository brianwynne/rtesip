import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const backendPort = process.env.RTESIP_PORT || '80'
const backendTarget = `http://localhost:${backendPort}`

export default defineConfig({
  plugins: [react()],
  server: {
    watch: {
      usePolling: true,
      interval: 500,
    },
    proxy: {
      '/api': {
        target: backendTarget,
        changeOrigin: true,
      },
      '/ws': {
        target: backendTarget.replace('http', 'ws'),
        ws: true,
      },
    },
  },
})
