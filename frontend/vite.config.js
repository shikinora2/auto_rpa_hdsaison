import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    setupFiles: './src/setupTests.js',
    globals: true,
    clearMocks: true,
    include: ['src/**/*.{test,spec}.{js,jsx,ts,tsx}', 'src/**/__tests__/**/*.{js,jsx,ts,tsx}'],
    exclude: ['**/node_modules/**', 'e2e/**'],
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true,
        changeOrigin: true,
      },
      '/downloads': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
