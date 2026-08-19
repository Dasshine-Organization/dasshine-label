import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

const stubAutomerge = process.env.VITE_E2E_STUB_AUTOMERGE === 'true'
const automergeEntry = stubAutomerge
  ? path.resolve(__dirname, './src/test/automergeStub.ts')
  : path.resolve(
      __dirname,
      'node_modules/@automerge/automerge/dist/mjs/entrypoints/fullfat_base64.js',
    )

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
      // Vite 5 rejects wasm-bindgen's ESM `.wasm` import (bundler build).
      // Base64 entry inlines WASM and works in both `vite` and `vite build`.
      '@automerge/automerge': automergeEntry,
    },
  },
  optimizeDeps: {
    exclude: stubAutomerge ? [] : ['@automerge/automerge'],
  },
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
