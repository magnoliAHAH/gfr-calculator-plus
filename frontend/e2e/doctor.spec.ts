import { expect, expectAccessible, test, uiLogin } from './fixtures';
import { AKI_CASE, calculate, fillCalcForm, OBESITY } from './helpers';

test.describe('врач: расчёт и решение', () => {
  test('логин → расчёт → принять', async ({ page, org }) => {
    await uiLogin(page, org.emails.physician);
    await expect(page).toHaveURL(/\/calculate$/);
    await fillCalcForm(page, OBESITY);
    await calculate(page);

    const card = page.getByTestId('result-recommendation');
    await expect(card).toBeVisible();
    await expect(page.getByTestId('dose-phrase')).toContainText(/1\s?350 мг каждые 12 ч/);
    await expect(card).toContainText('ABW');
    await expect(card).toContainText('Требуется контроль концентрации');
    await expect(page.getByTestId('audit-id')).toBeVisible();
    await expectAccessible(page);

    await page.getByRole('button', { name: /Принять \/ переопределить/ }).click();
    await page.getByRole('radio', { name: 'Принять рекомендацию' }).check();
    await page.getByRole('button', { name: 'Сохранить в аудит' }).click();
    await expect(card.getByText('Решение сохранено')).toBeVisible();
  });

  test('расчёт → переопределить с причиной, виден в аудите', async ({ page, org }) => {
    await uiLogin(page, org.emails.physician);
    await fillCalcForm(page, OBESITY);
    await calculate(page);
    await page.getByRole('button', { name: /Принять \/ переопределить/ }).click();

    await page.getByRole('radio', { name: 'Переопределить' }).check();
    await page.getByLabel('Категория причины').selectOption({ label: 'Клиническое суждение' });
    await page.getByLabel('Причина', { exact: true }).fill('abc');
    await page.getByRole('button', { name: 'Сохранить в аудит' }).click();
    await expect(page.getByText('Минимум 5 символов')).toBeVisible(); // валидация ≥ 5 символов (ТЗ 4.2)

    await page.getByLabel('Причина', { exact: true }).fill('Планируется CRRT');
    await page.getByRole('button', { name: 'Сохранить в аудит' }).click();
    await expect(page.getByText('Решение сохранено').first()).toBeVisible();

    await page.context().clearCookies();
    await page.evaluate(() => sessionStorage.clear());
    await uiLogin(page, org.emails.pharmacist);
    await page.goto('/audit');
    const row = page.getByRole('row', { name: /p_e2e/ });
    await expect(row).toContainText('Переопределено');
    await row.getByRole('link').click();
    await expect(page.getByText('Планируется CRRT')).toBeVisible();
    await page.getByRole('button', { name: 'Проверить цепочку' }).click();
    // Проверка идёт до выбранной записи включительно; расчёт — первая запись цепочки организации
    await expect(page.getByTestId('verify-result')).toContainText('Цепочка целостна: 1 записей');
  });

  test('fail-safe при AKI — красный блок, а не тост', async ({ page, org }) => {
    await uiLogin(page, org.emails.physician);
    await fillCalcForm(page, AKI_CASE);
    await calculate(page);

    const block = page.getByTestId('result-failsafe');
    await expect(block).toBeVisible();
    await expect(block).toContainText('Рекомендация не выдана');
    await expect(block).toContainText('Требуется консультация клинического фармаколога');
    await expect(page.locator('[data-sonner-toast][data-type="error"]')).toHaveCount(0);
    await expect(block.getByRole('button', { name: 'Позвать фармаколога' })).toBeVisible();
    await expect(block.getByRole('button', { name: /Зафиксировать отказ/ })).toBeVisible();
    await expectAccessible(page);

    await block.getByRole('button', { name: 'Позвать фармаколога' }).click();
    await expect(page.getByText(/уведомления не отправляются/)).toBeVisible(); // честная заглушка
  });

  test('валидация формы: диапазоны и обязательные поля', async ({ page, org }) => {
    await uiLogin(page, org.emails.physician);
    await calculate(page);
    await expect(page.getByText('Обязательное поле').first()).toBeVisible();
    await page.getByLabel(/^Вес/).fill('5');
    await calculate(page);
    await expect(page.getByText('Допустимо от 20 до 400')).toBeVisible();
  });

  test('врачу недоступны админские экраны', async ({ page, org }) => {
    await uiLogin(page, org.emails.physician);
    await page.goto('/admin/users');
    await expect(page).toHaveURL(/\/calculate$/);
    await expect(page.getByRole('link', { name: 'Дашборд' })).toHaveCount(0);
  });
});
