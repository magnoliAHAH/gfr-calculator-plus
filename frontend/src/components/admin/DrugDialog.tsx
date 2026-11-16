import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { api, unwrap, type Schemas } from '@/api/client';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent } from '@/components/ui/dialog';
import { Field, Input } from '@/components/ui/primitives';
import { t } from '@/i18n';
import { notifyError, notifySuccess } from '@/lib/notify';

type Drug = Schemas['DrugOut'];

interface FormValues {
  drug_code: string;
  drug_name: string;
  atc_code: string;
  route: string;
  formulation: string;
  rounding_step_mg: string;
}

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** null — создание нового препарата, иначе редактирование */
  drug: Drug | null;
}

const blank: FormValues = { drug_code: '', drug_name: '', atc_code: '', route: 'IV', formulation: '', rounding_step_mg: '250' };

const fromDrug = (d: Drug): FormValues => ({
  drug_code: d.drug_code, drug_name: d.drug_name, atc_code: d.atc_code ?? '', route: d.route,
  formulation: d.formulation ?? '', rounding_step_mg: String(d.rounding_step_mg),
});

export function DrugDialog({ open, onOpenChange, drug }: Props) {
  const qc = useQueryClient();
  const { register, handleSubmit, reset, formState: { errors } } = useForm<FormValues>({ defaultValues: blank });
  useEffect(() => { if (open) reset(drug ? fromDrug(drug) : blank); }, [open, drug, reset]);

  const save = useMutation({
    mutationFn: (v: FormValues) => {
      const common = {
        drug_name: v.drug_name.trim(), atc_code: v.atc_code.trim() || null, route: v.route.trim(),
        formulation: v.formulation.trim() || null, rounding_step_mg: Number(v.rounding_step_mg),
      };
      return drug
        ? unwrap(api.PATCH('/admin/drugs/{drug_id}', { params: { path: { drug_id: drug.id } }, body: common }))
        : unwrap(api.POST('/admin/drugs', { body: { drug_code: v.drug_code.trim(), ...common } }));
    },
    onSuccess: () => {
      notifySuccess(t('drugs.saved'));
      void qc.invalidateQueries({ queryKey: ['admin', 'drugs'] });
      void qc.invalidateQueries({ queryKey: ['meta', 'drugs'] });
      onOpenChange(false);
    },
    onError: notifyError,
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent title={drug ? t('drugs.edit') : t('drugs.add')}>
        <form onSubmit={handleSubmit((v) => save.mutate(v))} className="space-y-3" noValidate>
          <Field label={t('drugs.code')} hint={drug ? t('drugs.code.locked') : undefined} error={errors.drug_code?.message}>
            {(f) => (
              <Input id={f.id} disabled={drug !== null} aria-invalid={f.invalid} aria-describedby={f.describedBy}
                {...register('drug_code', { required: !drug && t('validation.required') })} />
            )}
          </Field>
          <Field label={t('drugs.name')} error={errors.drug_name?.message}>
            {(f) => <Input id={f.id} aria-invalid={f.invalid} aria-describedby={f.describedBy}
              {...register('drug_name', { required: t('validation.required') })} />}
          </Field>
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label={t('drugs.atc')}>{(f) => <Input id={f.id} maxLength={20} {...register('atc_code')} />}</Field>
            <Field label={t('drugs.route')} error={errors.route?.message}>
              {(f) => <Input id={f.id} aria-invalid={f.invalid} aria-describedby={f.describedBy}
                {...register('route', { required: t('validation.required') })} />}
            </Field>
          </div>
          <Field label={t('drugs.formulation')}>{(f) => <Input id={f.id} {...register('formulation')} />}</Field>
          <Field label={t('drugs.step')} hint={t('drugs.step.hint')} error={errors.rounding_step_mg?.message}>
            {(f) => (
              <Input id={f.id} type="number" step="any" min="0" aria-invalid={f.invalid} aria-describedby={f.describedBy}
                {...register('rounding_step_mg', { validate: (v) => Number(v) > 0 || t('validation.positive') })} />
            )}
          </Field>
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="outline" onClick={() => onOpenChange(false)}>{t('common.cancel')}</Button>
            <Button type="submit" disabled={save.isPending}>{t('common.save')}</Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
