import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

const stubAutomerge = process.env.VITE_E2E_STUB_AUTOMERGE === 'true'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
      ...(stubAutomerge
        ? { '@automerge/automerge': path.resolve(__dirname, './src/test/automergeStub.ts') }
        : {}),
    },
  },
  optimizeDeps: {
    exclude: stubAutomerge ? [] : ['@automerge/automerge'],
  },
  server: {
    port: 3000,
    hmr: { overlay: false },
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
