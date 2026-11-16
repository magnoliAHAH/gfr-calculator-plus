import type { FieldErrors, UseFormRegister } from 'react-hook-form';
import { useOverrideReasons } from '@/api/hooks';
import { Field, Input, Select, Textarea } from '@/components/ui/primitives';
import { t } from '@/i18n';

export type DecisionKind = 'accepted' | 'overridden' | 'contraindication_acknowledged';

export interface DecisionFormValues {
  decision: DecisionKind;
  override_reason_category: string;
  override_reason_text: string;
  new_dose_mg: string;
  new_frequency_hours: string;
}

export const MIN_TEXT = 5; // ТЗ 4.2: текст причины >= 5 символов

interface Props {
  decision: DecisionKind;
  register: UseFormRegister<DecisionFormValues>;
  errors: FieldErrors<DecisionFormValues>;
}

/** Поля, зависящие от выбранного решения: категория, новая доза, текст причины. */
export function OverrideFields({ decision, register, errors }: Props) {
  const reasons = useOverrideReasons();
  return (
    <>
      {decision === 'overridden' && (
        <>
          <Field label={t('decision.category')} error={errors.override_reason_category?.message}>
            {(f) => (
              <Select id={f.id} aria-invalid={f.invalid} aria-describedby={f.describedBy}
                {...register('override_reason_category', { required: t('validation.required') })}>
                <option value="">{t('common.choose')}</option>
                {(reasons.data ?? []).map((r) => (
                  <option key={r.code} value={r.code}>{r.display_name}</option>
                ))}
              </Select>
            )}
          </Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t('decision.newdose')} error={errors.new_dose_mg?.message}>
              {(f) => (
                <Input id={f.id} type="number" step="any" min="0" aria-invalid={f.invalid}
                  aria-describedby={f.describedBy}
                  {...register('new_dose_mg', {
                    validate: (v) => v === '' || Number(v) > 0 || t('validation.positive'),
                  })} />
              )}
            </Field>
            <Field label={t('decision.newfreq')} error={errors.new_frequency_hours?.message}>
              {(f) => (
                <Input id={f.id} type="number" step="1" min="1" aria-invalid={f.invalid}
                  aria-describedby={f.describedBy}
                  {...register('new_frequency_hours', {
                    validate: (v) =>
                      v === '' || (Number.isInteger(Number(v)) && Number(v) > 0) || t('validation.positive'),
                  })} />
              )}
            </Field>
          </div>
        </>
      )}
      {decision !== 'accepted' && (
        <Field label={t('decision.text')} error={errors.override_reason_text?.message}
          hint={decision === 'overridden' ? t('decision.text.hint', { min: MIN_TEXT }) : undefined}>
          {(f) => (
            <Textarea id={f.id} aria-invalid={f.invalid} aria-describedby={f.describedBy}
              {...register('override_reason_text', {
                validate: (v) => {
                  const len = v.trim().length;
                  if (decision === 'overridden') return len >= MIN_TEXT || t('validation.minlen', { min: MIN_TEXT });
                  return len > 0 || t('validation.required');
                },
              })} />
          )}
        </Field>
      )}
    </>
  );
}
