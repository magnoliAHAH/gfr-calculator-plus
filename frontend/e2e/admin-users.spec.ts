import { expect, expectAccessible, test, uiLogin } from './fixtures';

test.describe('администратор: пользователи', () => {
  test('пригласить пользователя и сменить ему роль', async ({ page, org }) => {
    await uiLogin(page, org.emails.org_admin);
    await page.goto('/admin/users');
    await page.getByRole('button', { name: 'Пригласить пользователя' }).first().click();
    const dialog = page.getByRole('dialog');
    await dialog.getByLabel('Email').fill(`new.${org.code}@test.local`);
    await dialog.getByLabel('Имя').fill('Новый Врач');
    await dialog.getByRole('button', { name: 'Пригласить', exact: true }).click();
    const note = page.getByTestId('invited');
    await expect(note).toContainText('Временный пароль');
    await expect(note).toContainText('показывается один раз');
    await expectAccessible(page);

    await page.getByLabel(/Роль: Новый Врач/).selectOption({ label: 'Аудитор' });
    await expect(page.getByText('Изменения сохранены')).toBeVisible();
  });

  test('временный пароль нужно сменить при первом входе', async ({ page, org }) => {
    const email = `fresh.${org.code}@test.local`;
    await uiLogin(page, org.emails.org_admin);
    await page.goto('/admin/users');
    await page.getByRole('button', { name: 'Пригласить пользователя' }).first().click();
    const dialog = page.getByRole('dialog');
    await dialog.getByLabel('Email').fill(email);
    await dialog.getByLabel('Имя').fill('Свежий Врач');
    await dialog.getByRole('button', { name: 'Пригласить', exact: true }).click();
    const temp = (await page.getByTestId('invited').locator('code').textContent()) ?? '';
    await page.evaluate(() => sessionStorage.clear());

    await uiLogin(page, email, temp);
    await expect(page).toHaveURL(/\/change-password$/);
    await page.goto('/calculate'); // попытка обойти смену пароля
    await expect(page).toHaveURL(/\/change-password$/);
    await page.getByLabel('Текущий пароль').fill(temp);
    await page.getByLabel('Новый пароль', { exact: true }).fill('Another-secure-pass-9');
    await page.getByLabel('Повторите новый пароль').fill('Another-secure-pass-9');
    await page.getByRole('button', { name: 'Сменить пароль' }).click();
    await expect(page).toHaveURL(/\/calculate$/);
  });

  test('нельзя отключить самого себя', async ({ page, org }) => {
    await uiLogin(page, org.emails.org_admin);
    await page.goto('/admin/users');
    const self = page.getByRole('row', { name: /Админ Тестов/ });
    await expect(self.getByRole('button', { name: 'Отключить' })).toHaveCount(0);
  });
});
