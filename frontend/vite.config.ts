/// <reference types="vitest/config" />
import path from 'node:path'
import tailwindcss from '@tailwindcss/vite'
import { tanstackRouter } from '@tanstack/router-plugin/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [
    // Must come before react(): generates src/routeTree.gen.ts from src/routes/.
    tanstackRouter({ target: 'react', autoCodeSplitting: false }),
    react(),
    tailwindcss(),
  ],
  resolve: {
    alias: { '@': path.resolve(import.meta.dirname, './src') },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['src/test-setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
    coverage: {
      provider: 'v8',
      // The escalation feature must be fully covered. The generated client, shadcn
      // components and the triage page are not part of this gate.
      include: [
        'src/components/escalation-card.tsx',
        'src/components/escalations-view.tsx',
        'src/components/escalations-page.tsx',
      ],
      thresholds: { lines: 100, functions: 100, branches: 100, statements: 100 },
    },
  },
  server: {
    // Proxy API calls to FastAPI in dev so the client can use relative URLs.
    // SSE (R2) passes through this proxy unchanged.
    proxy: { '/api': 'http://localhost:8000' },
  },
})
