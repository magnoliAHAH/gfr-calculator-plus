import { expect, expectAccessible, test } from './fixtures';

test.describe('demo mode (без входа)', () => {
  test('сценарий 1: ожирение → 1350 мг q12h, ABW', async ({ page }) => {
    await page.goto('/demo');
    await expect(page.getByTestId('scenario-obesity')).toBeVisible();
    await expectAccessible(page);

    await page.getByRole('button', { name: /сценарием «Ожирение»/ }).click();
    await page.getByRole('button', { name: 'Рассчитать' }).click();
    await expect(page.getByTestId('dose-phrase')).toContainText(/1\s?350 мг каждые 12 ч/);
    await expect(page.getByTestId('result-recommendation')).toContainText('ABW');
    await expect(page.getByTestId('demo-message')).toContainText('защищая от передозировки');
    // В demo нет аудита: ни кнопок решений, ни audit-ID
    await expect(page.getByRole('button', { name: /Принять \/ переопределить/ })).toHaveCount(0);
    await expect(page.getByTestId('audit-id')).toHaveCount(0);
  });

  test('сценарий 2: AKI → fail-safe', async ({ page }) => {
    await page.goto('/demo');
    await page.getByRole('button', { name: /сценарием «Острое повреждение почек»/ }).click();
    await page.getByRole('button', { name: 'Рассчитать' }).click();
    const block = page.getByTestId('result-failsafe');
    await expect(block).toContainText('Рекомендация не выдана');
    await expect(page.getByTestId('demo-message')).toContainText('нужен фармаколог');
    await expect(block.getByRole('button', { name: /Зафиксировать отказ/ })).toHaveCount(0);
  });

  test('сценарий 3: амикацин → 1050 мг q48h', async ({ page }) => {
    await page.goto('/demo');
    await page.getByRole('button', { name: /сценарием «Коррекция по функции почек»/ }).click();
    await page.getByRole('button', { name: 'Рассчитать' }).click();
    await expect(page.getByTestId('dose-phrase')).toContainText(/1\s?050 мг каждые 48 ч/);
    await expect(page.getByTestId('result-recommendation')).toContainText('Требуется контроль концентрации');
    await expect(page.getByTestId('demo-message')).toContainText('не стандартная');
  });

  test('demo работает без обращений к внешним серверам', async ({ page }) => {
    const external: string[] = [];
    page.on('request', (r) => {
      const url = new URL(r.url());
      if (url.hostname !== 'localhost' && url.hostname !== '127.0.0.1') external.push(r.url());
    });
    await page.goto('/demo');
    await page.getByRole('button', { name: /сценарием «Ожирение»/ }).click();
    await page.getByRole('button', { name: 'Рассчитать' }).click();
    await expect(page.getByTestId('dose-phrase')).toBeVisible();
    expect(external).toEqual([]);
  });

  test('не вошедший пользователь перенаправляется на логин', async ({ page }) => {
    await page.goto('/calculate');
    await expect(page).toHaveURL(/\/login$/);
    await expectAccessible(page);
  });

  test('неверный пароль: понятное сообщение, без перехода', async ({ page }) => {
    await page.goto('/login');
    await page.getByLabel('Email').fill('nobody@nowhere.test');
    await page.getByLabel('Пароль').fill('wrong-password');
    await page.getByRole('button', { name: 'Войти' }).click();
    await expect(page.getByRole('alert')).toContainText('Неверный email или пароль');
    await expect(page).toHaveURL(/\/login$/);
  });
});
