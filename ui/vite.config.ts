/// <reference types="vitest/config" />
import path from 'node:path'
import { execSync } from 'node:child_process'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// Phase 8 D-15: inject the short git SHA at build time so the bundled
// VersionIndicator component renders `v2.0 · <sha>`. Try/catch falls back
// to "unknown" so CI / detached builds never hard-fail. Both `npm run
// build` and `npm run build:mock` share this config, so both dists carry
// the same SHA automatically.
let gitSha: string
try {
  gitSha = execSync('git rev-parse --short HEAD').toString().trim()
} catch {
  gitSha = 'unknown'
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  define: {
    __GIT_SHA__: JSON.stringify(gitSha),
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test-setup.ts'],
  },
})
