import type { Page } from '@playwright/test';

export interface PatientInput {
  drug?: string;
  age: string;
  sex?: 'М' | 'Ж';
  weight?: string;
  height?: string;
  creatinine?: string;
  aki?: string;
  patientRef?: string;
}

/** Заполняет форму /calculate. Поля находятся по подписям, как их видит пользователь. */
export async function fillCalcForm(page: Page, p: PatientInput): Promise<void> {
  await page.getByLabel('Препарат').selectOption({ label: p.drug ?? 'Ванкомицин' });
  // «Показание» подставляется само, если оно единственное; ждём, пока список загрузится
  await page.getByLabel('Показание').selectOption({ index: 1 });
  await page.getByLabel(/^Возраст/).fill(p.age);
  await page.getByRole('radio', { name: p.sex ?? 'М' }).check();
  if (p.weight) await page.getByLabel(/^Вес/).fill(p.weight);
  if (p.height) await page.getByLabel(/^Рост/).fill(p.height);
  if (p.creatinine) await page.getByLabel(/^Креатинин/).fill(p.creatinine);
  if (p.aki) await page.getByLabel('Стадия ОПП (AKI)').selectOption({ label: p.aki });
  if (p.patientRef !== undefined) await page.getByLabel('ID пациента').fill(p.patientRef);
}

/** Сценарий 1 из ТЗ 4.7: ожирение, ABW 90 кг, 1350 мг q12h. */
export const OBESITY: PatientInput = {
  age: '45', weight: '120', height: '175', creatinine: '110.7', patientRef: 'p_e2e',
};

/** Сценарий 2: AKI стадия 2 — fail-safe. */
export const AKI_CASE: PatientInput = {
  age: '70', sex: 'Ж', weight: '60', creatinine: '175', aki: 'Стадия 2', patientRef: 'p_e2e_aki',
};

export async function calculate(page: Page): Promise<void> {
  await page.getByRole('button', { name: 'Рассчитать' }).click();
}
