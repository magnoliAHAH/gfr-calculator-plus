import type { Schemas } from '@/api/client';

export interface BracketForm {
  min_crcl: string;
  max_crcl: string;
  dose_per_kg: string;
  dose_mg: string;
  frequency_hours: string;
  tdm_required: boolean;
}

export interface RuleFormValues {
  indication: string;
  formula_code: string;
  weight_rule: string;
  max_allowed_aki: string;
  source: string;
  brackets: BracketForm[];
}

export const BLANK_BRACKET: BracketForm = {
  min_crcl: '', max_crcl: '', dose_per_kg: '', dose_mg: '', frequency_hours: '', tdm_required: false,
};

export const BLANK_RULE: RuleFormValues = {
  indication: '', formula_code: 'cockcroft_gault', weight_rule: 'auto', max_allowed_aki: 'stage_1', source: '',
  brackets: [{ ...BLANK_BRACKET }],
};

const num = (s: string): number | null => (s.trim() === '' ? null : Number(s));

export function toRuleSpec(v: RuleFormValues): Schemas['RuleVersionSpec'] {
  return {
    indication: v.indication.trim(), formula_code: v.formula_code, weight_rule: v.weight_rule,
    max_allowed_aki: v.max_allowed_aki, source: v.source.trim(),
    // Значения по умолчанию на сервере; в форме не редактируются, поэтому передаются явно
    min_age_years: 18, max_age_years: 120, pregnancy_contraindicated: false,
    brackets: v.brackets.map((b) => ({
      rrt_mode: 'none', min_crcl: num(b.min_crcl), max_crcl: num(b.max_crcl),
      dose_per_kg: num(b.dose_per_kg), dose_mg: num(b.dose_mg),
      frequency_hours: num(b.frequency_hours), infusion_duration_min: 60, tdm_required: b.tdm_required,
    })),
  };
}

/** Клиентская проверка перекрытия диапазонов CrCl (сервер проверяет то же независимо). */
export function bracketsOverlap(brackets: BracketForm[]): boolean {
  const ranges = brackets
    // Number('') === 0, поэтому пустые строки отбрасываем до приведения к числу
    .filter((b) => b.min_crcl.trim() !== '' && b.max_crcl.trim() !== '')
    .map((b) => [Number(b.min_crcl), Number(b.max_crcl)] as const)
    .filter(([a, b]) => !Number.isNaN(a) && !Number.isNaN(b))
    .sort((x, y) => x[0] - y[0]);
  return ranges.some((r, i) => i > 0 && r[0] < ranges[i - 1][1]);
}
