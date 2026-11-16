import { expect, expectAccessible, test, uiLogin } from './fixtures';
import { calculate } from './helpers';

test.describe('администратор: препараты и правила', () => {
  test('создать препарат → правило → проверить в расчёте', async ({ page, org }) => {
    await uiLogin(page, org.emails.org_admin);
    await page.goto('/admin/drugs');
    await expect(page.getByRole('heading', { name: 'Препараты' })).toBeVisible();
    await expectAccessible(page);

    await page.getByRole('button', { name: 'Добавить препарат' }).click();
    await page.getByLabel('Код препарата').fill('MERO_IV');
    await page.getByLabel('Название', { exact: true }).fill('Меропенем');
    await page.getByLabel('Шаг округления дозы, мг').fill('100');
    await page.getByRole('button', { name: 'Сохранить' }).click();
    const row = page.getByRole('row', { name: /MERO_IV/ });
    await expect(row).toBeVisible();

    await row.getByRole('link', { name: 'Правила' }).click();
    await page.getByRole('button', { name: 'Создать новую версию' }).click();
    const dialog = page.getByRole('dialog');
    await dialog.getByLabel('Показание').fill('sepsis_bacteremia');
    await dialog.getByLabel('Источник').fill('Протокол больницы 2026');
    await dialog.getByLabel('CrCl от').fill('0');
    await dialog.getByLabel('CrCl до').fill('999');
    await dialog.getByLabel('мг/кг').fill('20');
    await dialog.getByLabel('Каждые, ч').fill('8');
    await dialog.getByRole('button', { name: 'Создать версию' }).click();
    await expect(page.getByTestId('version-1')).toContainText('Действует');

    // Препарат сразу доступен врачу
    await page.evaluate(() => sessionStorage.clear());
    await uiLogin(page, org.emails.physician);
    await page.getByLabel('Препарат').selectOption({ label: 'Меропенем' });
    await page.getByLabel('Показание').selectOption({ index: 1 });
    await page.getByLabel(/^Возраст/).fill('50');
    await page.getByRole('radio', { name: 'М' }).check();
    await page.getByLabel(/^Вес/).fill('70');
    await page.getByLabel(/^Креатинин/).fill('80');
    await page.getByLabel('ID пациента').fill('p_mero');
    await calculate(page);
    await expect(page.getByTestId('dose-phrase')).toContainText(/1\s?400 мг каждые 8 ч/);
  });

  test('новая версия правила закрывает прежнюю', async ({ page, org }) => {
    await uiLogin(page, org.emails.pharmacist);
    await page.goto('/admin/drugs');
    await page.getByRole('row', { name: /VANCO_IV/ }).getByRole('link', { name: 'Правила' }).click();
    await expect(page.getByTestId('version-1')).toContainText('Действует');
    await page.getByRole('button', { name: 'Новая версия' }).click();
    const dialog = page.getByRole('dialog');
    await dialog.getByLabel('Источник').fill('Локальный протокол');
    await dialog.getByLabel('CrCl от').fill('0');
    await dialog.getByLabel('CrCl до').fill('999');
    await dialog.getByLabel('мг/кг').fill('10');
    await dialog.getByLabel('Каждые, ч').fill('12');
    await dialog.getByRole('button', { name: 'Создать версию' }).click();
    await expect(page.getByTestId('version-2')).toContainText('Действует');
    await expect(page.getByTestId('version-1')).toContainText('Закрыта');
  });

  test('фармаколог не меняет препараты, но видит правила', async ({ page, org }) => {
    await uiLogin(page, org.emails.pharmacist);
    await page.goto('/admin/drugs');
    await expect(page.getByRole('button', { name: 'Добавить препарат' })).toHaveCount(0);
    await expect(page.getByRole('link', { name: 'Правила' }).first()).toBeVisible();
  });

  test('импорт CSV создаёт новую версию, экспорт скачивается', async ({ page, org }) => {
    await uiLogin(page, org.emails.pharmacist);
    await page.goto('/admin/drugs');
    await page.getByRole('row', { name: /VANCO_IV/ }).getByRole('link', { name: 'Правила' }).click();

    const [download] = await Promise.all([
      page.waitForEvent('download'),
      page.getByRole('button', { name: 'Экспорт CSV' }).click(),
    ]);
    expect(download.suggestedFilename()).toBe('dosage_rules.csv');

    const csv = 'drug_code,indication,formula,weight_rule,min_crcl,max_crcl,dose_mg,frequency_hours,tdm,source,dose_per_kg\n'
      + 'VANCO_IV,sepsis_bacteremia,cockcroft_gault,tbw,0,999,,12,true,CSV-источник,10\n';
    await page.locator('input[type=file]').setInputFiles({
      name: 'rules.csv', mimeType: 'text/csv', buffer: Buffer.from(csv, 'utf-8'),
    });
    await expect(page.getByTestId('version-2')).toContainText('Действует');
  });
});
