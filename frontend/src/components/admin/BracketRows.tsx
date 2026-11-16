import { useFieldArray, type Control, type FieldErrors, type UseFormRegister } from 'react-hook-form';
import { Button } from '@/components/ui/button';
import { Field, Input } from '@/components/ui/primitives';
import { t } from '@/i18n';
import { BLANK_BRACKET, type RuleFormValues } from './ruleForm';

const NUMERIC = ['min_crcl', 'max_crcl', 'dose_per_kg', 'dose_mg', 'frequency_hours'] as const;

interface Props {
  control: Control<RuleFormValues>;
  register: UseFormRegister<RuleFormValues>;
  errors: FieldErrors<RuleFormValues>;
}

/** Динамический список диапазонов CrCl с дозой и кратностью. */
export function BracketRows({ control, register, errors }: Props) {
  const { fields, append, remove } = useFieldArray({ control, name: 'brackets' });
  return (
    <fieldset className="space-y-2">
      <legend className="text-sm font-semibold">{t('rules.brackets')}</legend>
      {fields.map((field, i) => (
        <div key={field.id} className="grid items-end gap-2 rounded-md border border-border p-2 sm:grid-cols-7">
          {NUMERIC.map((name) => (
            <Field key={name} label={t(`rules.col.${name}`)} error={errors.brackets?.[i]?.[name]?.message}>
              {(f) => (
                <Input id={f.id} type="number" step="any" min="0" aria-invalid={f.invalid}
                  aria-describedby={f.describedBy}
                  {...register(`brackets.${i}.${name}`, {
                    validate: (val) => {
                      const required = name === 'min_crcl' || name === 'max_crcl';
                      if (val === '') return !required || t('validation.required');
                      return Number(val) >= 0 || t('validation.positive');
                    },
                  })} />
              )}
            </Field>
          ))}
          <label className="flex items-center gap-2 pb-2 text-sm">
            <input type="checkbox" {...register(`brackets.${i}.tdm_required`)} /> {t('rules.col.tdm')}
          </label>
          <Button variant="ghost" size="sm" disabled={fields.length === 1} onClick={() => remove(i)}
            aria-label={t('rules.removebracket', { n: i + 1 })}>✕</Button>
        </div>
      ))}
      <Button variant="outline" size="sm" onClick={() => append({ ...BLANK_BRACKET })}>{t('rules.addbracket')}</Button>
      <p className="text-xs text-muted-foreground">{t('rules.dosehint')}</p>
    </fieldset>
  );
}
