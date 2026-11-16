import { defineConfig, devices } from '@playwright/test';

/**
 * E2E идут против РАЗВЁРНУТОГО стека (docker compose up), а не против dev-сервера:
 * так проверяются nginx-проксирование, CSP и реальная БД.
 * Переменные: E2E_BASE_URL (по умолчанию http://localhost:8082),
 * E2E_SUPER_EMAIL / E2E_SUPER_PASSWORD (super_admin, создаёт тестовые организации).
 */
export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  expect: { timeout: 7_000 },
  fullyParallel: false, // тесты делят одну организацию и правят данные (правила, пользователи)
  workers: 1,
  retries: 0,
  reporter: [['list']],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? 'http://localhost:8082',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    locale: 'ru-RU',
    // Планшет 1024px должен работать (ТЗ 7.9); десктоп — основной режим
    viewport: { width: 1280, height: 800 },
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'], viewport: { width: 1280, height: 800 } } }],
});
