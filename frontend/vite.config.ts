import react from '@vitejs/plugin-react';
import { fileURLToPath, URL } from 'node:url';
import { defineConfig } from 'vitest/config';

// Dev: /api проксируется на бэкенд (по умолчанию docker compose api на 8000).
const target = process.env.VITE_DEV_PROXY ?? 'http://localhost:8000';

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) } },
  server: {
    port: 5173,
    proxy: { '/api': target, '/health': target, '/docs': target, '/openapi.json': target },
  },
  // threads: форк-пул vitest 2 падает на Windows + Node 20.9 (путь с кириллицей/OneDrive)
  test: { environment: 'node', include: ['src/**/*.test.ts'], pool: 'threads' },
});
