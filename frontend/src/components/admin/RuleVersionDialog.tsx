import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { api, unwrap } from '@/api/client';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent } from '@/components/ui/dialog';
import { Field, Input, Select } from '@/components/ui/primitives';
import { t } from '@/i18n';
import { notifyError, notifySuccess } from '@/lib/notify';
import { BracketRows } from './BracketRows';
import { BLANK_BRACKET, BLANK_RULE, bracketsOverlap, toRuleSpec, type RuleFormValues } from './ruleForm';

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  drugId: number;
  /** Показание, для которого создаётся новая версия (null — новое показание). */
  indication: string | null;
}

const WEIGHT_RULES = ['auto', 'tbw', 'ibw', 'abw'] as const;
const AKI = ['none', 'stage_1', 'stage_2', 'stage_3'] as const;

export function RuleVersionDialog({ open, onOpenChange, drugId, indication }: Props) {
  const qc = useQueryClient();
  const { register, handleSubmit, reset, control, setError, formState: { errors } } =
    useForm<RuleFormValues>({ defaultValues: BLANK_RULE });
  useEffect(() => {
    if (open) reset({ ...BLANK_RULE, indication: indication ?? '', brackets: [{ ...BLANK_BRACKET }] });
  }, [open, indication, reset]);

  const save = useMutation({
    mutationFn: (v: RuleFormValues) =>
      unwrap(api.POST('/admin/drugs/{drug_id}/rules', { params: { path: { drug_id: drugId } }, body: toRuleSpec(v) })),
    onSuccess: (r) => {
      notifySuccess(t('rules.created', { version: r.version }));
      void qc.invalidateQueries({ queryKey: ['admin', 'rules', drugId] });
      void qc.invalidateQueries({ queryKey: ['meta', 'indications'] });
      onOpenChange(false);
    },
    onError: notifyError,
  });

  const submit = (v: RuleFormValues) => {
    if (bracketsOverlap(v.brackets)) {
      setError('brackets', { message: t('rules.overlap') });
      return;
    }
    save.mutate(v);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent title={t('rules.new')} description={t('rules.new.hint')} className="max-w-3xl">
        <form onSubmit={handleSubmit(submit)} className="space-y-3" noValidate>
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label={t('rules.indication')} error={errors.indication?.message}>
              {(f) => <Input id={f.id} aria-invalid={f.invalid} aria-describedby={f.describedBy}
                {...register('indication', { required: t('validation.required') })} />}
            </Field>
            <Field label={t('rules.source')} error={errors.source?.message}>
              {(f) => <Input id={f.id} aria-invalid={f.invalid} aria-describedby={f.describedBy}
                {...register('source', { required: t('validation.required') })} />}
            </Field>
            <Field label={t('rules.formula')}>
              {(f) => (
                <Select id={f.id} {...register('formula_code')}>
                  <option value="cockcroft_gault">Cockcroft-Gault</option>
                  <option value="ckd_epi_2021">CKD-EPI 2021</option>
                </Select>
              )}
            </Field>
            <Field label={t('rules.weightrule')}>
              {(f) => (
                <Select id={f.id} {...register('weight_rule')}>
                  {WEIGHT_RULES.map((w) => <option key={w} value={w}>{t(`weightrule.${w}`)}</option>)}
                </Select>
              )}
            </Field>
            <Field label={t('rules.maxaki')}>
              {(f) => (
                <Select id={f.id} {...register('max_allowed_aki')}>
                  {AKI.map((a) => <option key={a} value={a}>{t(`aki.${a}`)}</option>)}
                </Select>
              )}
            </Field>
          </div>

          <BracketRows control={control} register={register} errors={errors} />
          {errors.brackets?.message && (
            <p role="alert" className="text-sm text-destructive">{errors.brackets.message}</p>
          )}

          <div className="flex justify-end gap-2 pt-2">
            <Button variant="outline" onClick={() => onOpenChange(false)}>{t('common.cancel')}</Button>
            <Button type="submit" disabled={save.isPending}>{t('rules.create')}</Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
