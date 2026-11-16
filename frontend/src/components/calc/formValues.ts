import type { Schemas } from '@/api/client';
import { toOptionalNumber } from '@/lib/utils';

/** Значения полей формы. Числа хранятся строками: пустое поле = «не указано». */
export interface CalcFormValues {
  drug_code: string;
  indication: string;
  age_years: string;
  sex_at_birth: 'male' | 'female' | '';
  weight_kg: string;
  height_cm: string;
  creatinine_umol_l: string;
  aki_stage: Schemas['CalculateRequest']['aki_stage'];
  rrt_mode: Schemas['CalculateRequest']['rrt_mode'];
  pregnancy: boolean;
  ecmo: boolean;
  patient_ref: string;
}

export const EMPTY_VALUES: CalcFormValues = {
  drug_code: '', indication: '', age_years: '', sex_at_birth: '', weight_kg: '', height_cm: '',
  creatinine_umol_l: '', aki_stage: 'none', rrt_mode: 'none', pregnancy: false, ecmo: false, patient_ref: '',
};

/** Диапазоны из ТЗ 4.1.1; дублируют серверную валидацию для быстрой обратной связи. */
export const RANGES = {
  age_years: { min: 0, max: 120 },
  weight_kg: { min: 20, max: 400 },
  height_cm: { min: 100, max: 250 },
  creatinine_umol_l: { min: 10, max: 3000 },
} as const;

export type RangedField = keyof typeof RANGES;

/** Сообщение об ошибке диапазона либо undefined, если значение допустимо. */
export function rangeError(field: RangedField, raw: string, required: boolean): 'required' | 'range' | undefined {
  const n = toOptionalNumber(raw);
  if (n === undefined) return required ? 'required' : undefined;
  const { min, max } = RANGES[field];
  return Number.isNaN(n) || n < min || n > max ? 'range' : undefined;
}

export function toRequest(v: CalcFormValues): Schemas['CalculateRequest'] {
  return {
    drug_code: v.drug_code,
    indication: v.indication,
    age_years: Number(v.age_years),
    sex_at_birth: v.sex_at_birth as 'male' | 'female',
    weight_kg: toOptionalNumber(v.weight_kg) ?? null,
    height_cm: toOptionalNumber(v.height_cm) ?? null,
    creatinine_umol_l: toOptionalNumber(v.creatinine_umol_l) ?? null,
    aki_stage: v.aki_stage,
    rrt_mode: v.rrt_mode,
    pregnancy: v.pregnancy,
    ecmo: v.ecmo,
    patient_ref: v.patient_ref.trim(),
  };
}

/** Тот же запрос без patient_ref — для публичного demo. */
export function toDemoRequest(v: CalcFormValues): Schemas['DemoCalculateRequest'] {
  const { patient_ref: _ignored, ...rest } = toRequest(v);
  return rest;
}

/** Предзаполнение формы из demo-сценария. */
export function valuesFromScenario(r: Schemas['DemoCalculateRequest']): CalcFormValues {
  const s = (n: number | null | undefined): string => (n === null || n === undefined ? '' : String(n));
  return {
    drug_code: r.drug_code, indication: r.indication, age_years: s(r.age_years), sex_at_birth: r.sex_at_birth,
    weight_kg: s(r.weight_kg), height_cm: s(r.height_cm), creatinine_umol_l: s(r.creatinine_umol_l),
    aki_stage: r.aki_stage ?? 'none', rrt_mode: r.rrt_mode ?? 'none', pregnancy: r.pregnancy ?? false,
    ecmo: r.ecmo ?? false, patient_ref: '',
  };
}
