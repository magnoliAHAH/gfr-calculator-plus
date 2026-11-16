import { useMutation } from '@tanstack/react-query';
import { useForm, useWatch } from 'react-hook-form';
import { api, ApiProblem, unwrap, type Schemas } from '@/api/client';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent } from '@/components/ui/dialog';
import { t } from '@/i18n';
import { notifyError, notifySuccess } from '@/lib/notify';
import { OverrideFields, type DecisionFormValues, type DecisionKind } from './OverrideFields';

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  auditId: number;
  /** У fail-safe нечего «принимать»: остаются «переопределить» и «отклонить». */
  allowAccept: boolean;
  onSaved: () => void;
}

function toBody(v: DecisionFormValues): Schemas['DecisionRequest'] {
  const body: Schemas['DecisionRequest'] = { decision: v.decision };
  if (v.decision === 'overridden') {
    body.override_reason_category = v.override_reason_category;
    body.override_reason_text = v.override_reason_text.trim();
    if (v.new_dose_mg !== '') body.new_dose_mg = Number(v.new_dose_mg);
    if (v.new_frequency_hours !== '') body.new_frequency_hours = Number(v.new_frequency_hours);
  } else if (v.decision === 'contraindication_acknowledged') {
    body.override_reason_text = v.override_reason_text.trim();
  }
  return body;
}

export function DecisionDialog({ open, onOpenChange, auditId, allowAccept, onSaved }: Props) {
  const {
    register, handleSubmit, control, formState: { errors },
  } = useForm<DecisionFormValues>({
    defaultValues: {
      decision: allowAccept ? 'accepted' : 'overridden', override_reason_category: '',
      override_reason_text: '', new_dose_mg: '', new_frequency_hours: '',
    },
  });
  const decision = useWatch({ control, name: 'decision' });

  const save = useMutation({
    mutationFn: (v: DecisionFormValues) =>
      unwrap(api.POST('/audit/{audit_id}/decision', {
        params: { path: { audit_id: auditId } }, body: toBody(v),
      })),
    onSuccess: () => {
      notifySuccess(t('decision.saved'));
      onOpenChange(false);
      onSaved();
    },
    onError: (err) => {
      notifyError(err);
      // 409: решение уже есть (например, принято в другой вкладке) — закрываем окно, родитель обновит статус
      if (err instanceof ApiProblem && err.status === 409) {
        onOpenChange(false);
        onSaved();
      }
    },
  });

  const options: { value: DecisionKind; label: string }[] = [
    ...(allowAccept ? [{ value: 'accepted' as const, label: t('decision.opt.accepted') }] : []),
    { value: 'overridden', label: t('decision.opt.overridden') },
    { value: 'contraindication_acknowledged', label: t('decision.opt.contra') },
  ];

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent title={t('decision.title')} description={t('decision.description')}>
        <form onSubmit={handleSubmit((v) => save.mutate(v))} className="space-y-4" noValidate>
          <fieldset className="space-y-2">
            <legend className="text-sm font-medium">{t('decision.choose')}</legend>
            {options.map((o) => (
              <label key={o.value} className="flex items-center gap-2 text-sm">
                <input type="radio" value={o.value} {...register('decision')} />
                {o.label}
              </label>
            ))}
          </fieldset>

          <OverrideFields decision={decision} register={register} errors={errors} />

          <div className="flex justify-end gap-2 pt-2">
            <Button variant="outline" onClick={() => onOpenChange(false)}>{t('common.cancel')}</Button>
            <Button type="submit" disabled={save.isPending}>{t('decision.save')}</Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
