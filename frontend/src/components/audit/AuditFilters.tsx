import { useForm } from 'react-hook-form';
import { useDrugs } from '@/api/hooks';
import { Button } from '@/components/ui/button';
import { Card, Field, Input, Select } from '@/components/ui/primitives';
import { t, tDynamic } from '@/i18n';

export interface Filters {
  from: string;
  to: string;
  drug: string;
  decision: string;
  patient_ref: string;
}

export const EMPTY_FILTERS: Filters = { from: '', to: '', drug: '', decision: '', patient_ref: '' };
const DECISIONS = ['pending', 'accepted', 'overridden', 'contraindication_acknowledged'] as const;

export function AuditFilters({ onApply }: { onApply: (f: Filters) => void }) {
  const drugs = useDrugs();
  const { register, handleSubmit, reset } = useForm<Filters>({ defaultValues: EMPTY_FILTERS });
  return (
    <Card>
      <form onSubmit={handleSubmit(onApply)} className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5"
        aria-label={t('audit.filters')}>
        <Field label={t('audit.from')}>{(f) => <Input id={f.id} type="date" {...register('from')} />}</Field>
        <Field label={t('audit.to')}>{(f) => <Input id={f.id} type="date" {...register('to')} />}</Field>
        <Field label={t('audit.drug')}>
          {(f) => (
            <Select id={f.id} {...register('drug')}>
              <option value="">{t('common.all')}</option>
              {(drugs.data ?? []).map((d) => <option key={d.drug_code} value={d.drug_code}>{d.drug_name}</option>)}
            </Select>
          )}
        </Field>
        <Field label={t('audit.decision')}>
          {(f) => (
            <Select id={f.id} {...register('decision')}>
              <option value="">{t('common.all')}</option>
              {DECISIONS.map((d) => <option key={d} value={d}>{tDynamic('decision', d)}</option>)}
            </Select>
          )}
        </Field>
        <Field label={t('audit.patient')}>
          {(f) => <Input id={f.id} autoComplete="off" {...register('patient_ref')} />}
        </Field>
        <div className="flex gap-2 sm:col-span-2 lg:col-span-5">
          <Button type="submit">{t('audit.apply')}</Button>
          <Button variant="outline" onClick={() => { reset(EMPTY_FILTERS); onApply(EMPTY_FILTERS); }}>
            {t('audit.reset')}
          </Button>
        </div>
      </form>
    </Card>
  );
}
