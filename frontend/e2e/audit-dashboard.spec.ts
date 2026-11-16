import { expect, expectAccessible, test, uiLogin } from './fixtures';
import { AKI_CASE, calculate, fillCalcForm, OBESITY } from './helpers';

/** Врач делает расчёт и сохраняет решение; возвращает управление на странице аудитора. */
async function seedAudit(page: import('@playwright/test').Page, email: string): Promise<void> {
  await uiLogin(page, email);
  await fillCalcForm(page, { ...OBESITY, patientRef: 'p_dash_1' });
  await calculate(page);
  await page.getByRole('button', { name: /Принять \/ переопределить/ }).click();
  await page.getByRole('radio', { name: 'Принять рекомендацию' }).check();
  await page.getByRole('button', { name: 'Сохранить в аудит' }).click();
  await expect(page.getByText('Решение сохранено').first()).toBeVisible();

  await page.reload(); // форма сбрасывается, но токен остаётся
  await fillCalcForm(page, { ...AKI_CASE, patientRef: 'p_dash_2' });
  await calculate(page);
  await expect(page.getByTestId('result-failsafe')).toBeVisible();
  await page.evaluate(() => sessionStorage.clear());
}

test.describe('аудит и дашборд', () => {
  test('список аудита: фильтры, бейдж целостности, детали', async ({ page, org }) => {
    await seedAudit(page, org.emails.physician);
    await uiLogin(page, org.emails.auditor);
    await page.goto('/audit');

    await expect(page.getByTestId('chain-badge')).toContainText('Цепочка целостна: 3 записей');
    await expect(page.getByRole('row', { name: /p_dash_1/ })).toContainText('Принято');
    await expect(page.getByRole('row', { name: /p_dash_2/ })).toContainText('Fail-safe');
    await expectAccessible(page);

    await page.getByLabel('ID пациента').fill('p_dash_1');
    await page.getByRole('button', { name: 'Применить' }).click();
    await expect(page.getByRole('row', { name: /p_dash_2/ })).toHaveCount(0);
    await expect(page.getByRole('row', { name: /p_dash_1/ })).toBeVisible();

    await page.getByRole('row', { name: /p_dash_1/ }).getByRole('link').click();
    await expect(page.getByRole('heading', { name: /Запись аудита №/ })).toBeVisible();
    await expect(page.getByText('Входные данные')).toBeVisible();
    await expectAccessible(page);
  });

  test('врач видит только свои записи аудита и не видит бейдж цепочки', async ({ page, org }) => {
    await seedAudit(page, org.emails.physician);
    await uiLogin(page, org.emails.physician);
    await page.goto('/audit');
    await expect(page).toHaveURL(/\/calculate$/); // у врача нет экрана аудита (ТЗ 7.1)
  });

  test('дашборд: метрики, период, экспорт', async ({ page, org }) => {
    await seedAudit(page, org.emails.physician);
    await uiLogin(page, org.emails.org_admin);
    await page.goto('/dashboard');

    await expect(page.getByTestId('stat-total')).toContainText('2');
    await expect(page.getByTestId('stat-accepted')).toContainText('50');
    await expect(page.getByTestId('stat-failsafe')).toContainText('50');
    await expect(page.getByRole('figure', { name: 'Топ препаратов' })).toBeVisible();
    await expect(page.getByTestId('chain-badge')).toContainText('Цепочка целостна');
    await expectAccessible(page);

    await page.getByRole('tab', { name: '7 дней' }).click();
    await expect(page.getByRole('tab', { name: '7 дней' })).toHaveAttribute('aria-selected', 'true');
    await expect(page.getByTestId('stat-total')).toContainText('2');

    const [download] = await Promise.all([
      page.waitForEvent('download'),
      page.getByRole('button', { name: 'Экспорт CSV' }).click(),
    ]);
    expect(download.suggestedFilename()).toBe('dashboard-7d.csv');
  });

  test('аудитор не может считать, а врач не видит дашборд', async ({ page, org }) => {
    await uiLogin(page, org.emails.auditor);
    await page.goto('/calculate');
    await expect(page).toHaveURL(/\/audit$/);
    await page.evaluate(() => sessionStorage.clear());
    await uiLogin(page, org.emails.physician);
    await page.goto('/dashboard');
    await expect(page).toHaveURL(/\/calculate$/);
  });
});
