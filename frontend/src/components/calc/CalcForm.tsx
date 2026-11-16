import { useEffect } from 'react';
import { useForm, useWatch } from 'react-hook-form';
import { useIndications } from '@/api/hooks';
import { Button } from '@/components/ui/button';
import { Field, Input, Select } from '@/components/ui/primitives';
import { t } from '@/i18n';
import { ContextFields } from './ContextFields';
import { type CalcFormValues } from './formValues';
import { NumberField } from './NumberField';

export interface DrugOption {
  drug_code: string;
  drug_name: string;
}

interface Props {
  drugs: DrugOption[];
  /** Для /demo: показания известны заранее; иначе грузятся с сервера по препарату. */
  demoIndications?: Record<string, string[]>;
  initial: CalcFormValues;
  /** Поле «ID пациента» нужно только в боевом режиме (в demo аудита нет). */
  showPatientRef: boolean;
  serverErrors?: Record<string, string>;
  submitting: boolean;
  onSubmit: (v: CalcFormValues) => void;
}

function useIndicationList(drugCode: string, demo?: Record<string, string[]>) {
  const server = useIndications(demo ? '' : drugCode);
  if (demo) return { items: demo[drugCode] ?? [], loading: false };
  return { items: server.data ?? [], loading: server.isLoading };
}

type NumName = 'age_years' | 'weight_kg' | 'height_cm' | 'creatinine_umol_l';

export function CalcForm({ drugs, demoIndications, initial, showPatientRef, serverErrors, submitting, onSubmit }: Props) {
  const {
    register, handleSubmit, setValue, control, reset, formState: { errors },
  } = useForm<CalcFormValues>({ defaultValues: initial });

  useEffect(() => reset(initial), [initial, reset]); // предзаполнение из demo-сценария

  const drugCode = useWatch({ control, name: 'drug_code' });
  const indication = useWatch({ control, name: 'indication' });
  const { items: indications, loading } = useIndicationList(drugCode, demoIndications);

  // Зависимый список: показание сбрасывается при смене препарата; единственное — выбирается само
  useEffect(() => {
    if (indications.length === 0) return;
    if (!indications.includes(indication)) setValue('indication', indications.length === 1 ? indications[0] : '');
  }, [indications, indication, setValue]);

  const num = (name: NumName, label: string, unit: string, required: boolean) => (
    <NumberField name={name} label={label} unit={unit} required={required} register={register}
      errors={errors} serverError={serverErrors?.[name]} />
  );

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate aria-label={t('calc.form')}>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label={t('calc.drug')} error={errors.drug_code?.message}>
          {(f) => (
            <Select id={f.id} aria-invalid={f.invalid} aria-describedby={f.describedBy}
              {...register('drug_code', { required: t('validation.required') })}>
              <option value="">{t('common.choose')}</option>
              {drugs.map((d) => <option key={d.drug_code} value={d.drug_code}>{d.drug_name}</option>)}
            </Select>
          )}
        </Field>
        <Field label={t('calc.indication')} error={errors.indication?.message ?? serverErrors?.indication}>
          {(f) => (
            <Select id={f.id} disabled={!drugCode || loading} aria-invalid={f.invalid}
              aria-describedby={f.describedBy}
              {...register('indication', { required: t('validation.required') })}>
              <option value="">{t('common.choose')}</option>
              {indications.map((i) => <option key={i} value={i}>{i}</option>)}
            </Select>
          )}
        </Field>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        {num('age_years', t('calc.age'), t('unit.years'), true)}
        <fieldset>
          <legend className="text-sm font-medium">{t('calc.sex')}</legend>
          <div className="mt-2 flex gap-4">
            {(['male', 'female'] as const).map((s) => (
              <label key={s} className="flex items-center gap-2 text-sm">
                <input type="radio" value={s} {...register('sex_at_birth', { required: t('validation.required') })} />
                {t(s === 'male' ? 'calc.sex.male' : 'calc.sex.female')}
              </label>
            ))}
          </div>
          {errors.sex_at_birth && (
            <p role="alert" className="mt-1 text-sm text-destructive">{errors.sex_at_birth.message}</p>
          )}
        </fieldset>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        {num('weight_kg', t('calc.weight'), t('unit.kg'), false)}
        {num('height_cm', t('calc.height'), t('unit.cm'), false)}
        {num('creatinine_umol_l', t('calc.creatinine'), t('unit.umol'), false)}
      </div>
      <p className="text-xs text-muted-foreground">{t('calc.optional.hint')}</p>

      <ContextFields register={register} />

      {showPatientRef && (
        <Field label={t('calc.patient')} hint={t('calc.patient.hint')}
          error={errors.patient_ref?.message ?? serverErrors?.patient_ref}>
          {(f) => (
            <Input id={f.id} maxLength={100} autoComplete="off" aria-invalid={f.invalid}
              aria-describedby={f.describedBy}
              {...register('patient_ref', { validate: (v) => v.trim() !== '' || t('validation.required') })} />
          )}
        </Field>
      )}

      <Button type="submit" size="lg" className="w-full" disabled={submitting}>
        {submitting ? t('calc.calculating') : t('calc.submit')}
      </Button>
    </form>
  );
}
