import type { FieldErrors, UseFormRegister } from 'react-hook-form';
import { Field, Input } from '@/components/ui/primitives';
import { t } from '@/i18n';
import { RANGES, rangeError, type CalcFormValues, type RangedField } from './formValues';

interface Props {
  name: RangedField;
  label: string;
  unit: string;
  required: boolean;
  register: UseFormRegister<CalcFormValues>;
  errors: FieldErrors<CalcFormValues>;
  serverError?: string;
}

/** Числовое поле с проверкой диапазона из ТЗ 4.1.1 (дублирует серверную валидацию). */
export function NumberField({ name, label, unit, required, register, errors, serverError }: Props) {
  return (
    <Field label={`${label}, ${unit}`} error={errors[name]?.message ?? serverError}>
      {(f) => (
        <Input
          id={f.id} type="number" inputMode="decimal" step="any" aria-invalid={f.invalid}
          aria-describedby={f.describedBy}
          {...register(name, {
            validate: (raw) => {
              const e = rangeError(name, raw, required);
              if (e === 'required') return t('validation.required');
              if (e === 'range') return t('validation.range', { min: RANGES[name].min, max: RANGES[name].max });
              return true;
            },
          })}
        />
      )}
    </Field>
  );
}
