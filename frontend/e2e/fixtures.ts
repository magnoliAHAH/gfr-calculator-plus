import { expect, request, test as base, type APIRequestContext, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

const BASE = process.env.E2E_BASE_URL ?? 'http://localhost:8082';
const SUPER_EMAIL = process.env.E2E_SUPER_EMAIL ?? 'root@e2e.test';
const SUPER_PASSWORD = process.env.E2E_SUPER_PASSWORD ?? 'E2e-root-pass-1';

export const PASSWORD = 'E2e-user-pass-123';
export type RoleName = 'org_admin' | 'pharmacist' | 'physician' | 'auditor';

export interface TestOrg {
  code: string;
  emails: Record<RoleName, string>;
}

async function login(api: APIRequestContext, email: string, password: string): Promise<string> {
  const r = await api.post('/api/v1/auth/login', { data: { email, password } });
  expect(r.ok(), `login ${email}: ${r.status()}`).toBeTruthy();
  return (await r.json()).access_token as string;
}

/** Создаёт организацию через API, как это сделал бы super_admin, и сразу снимает флаг смены пароля. */
export async function createOrg(): Promise<TestOrg> {
  const api = await request.newContext({ baseURL: BASE });
  const sa = await login(api, SUPER_EMAIL, SUPER_PASSWORD);
  const code = `e2e${Date.now().toString(36)}${Math.floor(Math.random() * 1000)}`;
  const adminEmail = `org_admin@${code}.test`;
  const created = await api.post('/api/v1/admin/organizations', {
    headers: { Authorization: `Bearer ${sa}` },
    data: { name: `E2E ${code}`, code, admin_email: adminEmail, admin_full_name: 'Админ Тестов' },
  });
  expect(created.status()).toBe(201);
  const temp = (await created.json()).temp_password as string;

  const adminToken = await login(api, adminEmail, temp);
  const change = async (token: string, current: string) => {
    const r = await api.post('/api/v1/auth/change-password', {
      headers: { Authorization: `Bearer ${token}` }, data: { current_password: current, new_password: PASSWORD },
    });
    expect(r.status()).toBe(204);
  };
  await change(adminToken, temp);

  const emails = { org_admin: adminEmail } as Record<RoleName, string>;
  const token = await login(api, adminEmail, PASSWORD);
  const names: Record<string, string> = { pharmacist: 'Фармакологов Ф.Ф.', physician: 'Врачев В.В.', auditor: 'Аудитов А.А.' };
  for (const role of ['pharmacist', 'physician', 'auditor'] as const) {
    const email = `${role}@${code}.test`;
    const inv = await api.post('/api/v1/admin/users', {
      headers: { Authorization: `Bearer ${token}` }, data: { email, full_name: names[role], role },
    });
    expect(inv.status()).toBe(201);
    const userTemp = (await inv.json()).temp_password as string;
    await change(await login(api, email, userTemp), userTemp);
    emails[role] = email;
  }
  await api.dispose();
  return { code, emails };
}

export async function uiLogin(page: Page, email: string, password = PASSWORD): Promise<void> {
  await page.goto('/login');
  await page.getByLabel('Email').fill(email);
  await page.getByLabel('Пароль').fill(password);
  await page.getByRole('button', { name: 'Войти' }).click();
  // Ждём завершения входа: иначе следующий goto прервёт запрос логина до сохранения токена
  await page.waitForURL((url) => !url.pathname.startsWith('/login'));
}

/** Проверка доступности (WCAG A/AA) текущей страницы; падает при любом нарушении. */
export async function expectAccessible(page: Page): Promise<void> {
  const results = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze();
  const summary = results.violations.map((v) => `${v.id} (${v.impact}): ${v.nodes.length} elem. — ${v.help}`);
  expect(summary, `a11y нарушения:\n${summary.join('\n')}`).toEqual([]);
}

export const test = base.extend<{ org: TestOrg }>({
  org: async ({}, use) => {
    await use(await createOrg());
  },
});
export { expect };
