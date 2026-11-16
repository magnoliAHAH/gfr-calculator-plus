import type { UseFormRegister } from 'react-hook-form';
import { Field, Select } from '@/components/ui/primitives';
import { t } from '@/i18n';
import type { CalcFormValues } from './formValues';

const AKI = ['none', 'stage_1', 'stage_2', 'stage_3'] as const;
const RRT = ['none', 'hd', 'pd', 'cvvh', 'cvvhd', 'cvvhdf'] as const;

/** Стадия AKI, режим RRT, беременность и ECMO: обязательные клинические поля (ТЗ 4.1.1). */
export function ContextFields({ register }: { register: UseFormRegister<CalcFormValues> }) {
  return (
    <>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label={t('calc.aki')}>
          {(f) => (
            <Select id={f.id} {...register('aki_stage')}>
              {AKI.map((a) => <option key={a} value={a}>{t(`aki.${a}`)}</option>)}
            </Select>
          )}
        </Field>
        <Field label={t('calc.rrt')}>
          {(f) => (
            <Select id={f.id} {...register('rrt_mode')}>
              {RRT.map((r) => <option key={r} value={r}>{t(`rrt.${r}`)}</option>)}
            </Select>
          )}
        </Field>
      </div>
      <div className="flex flex-wrap gap-6">
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" {...register('pregnancy')} /> {t('calc.pregnancy')}
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" {...register('ecmo')} /> {t('calc.ecmo')}
        </label>
      </div>
    </>
  );
}
