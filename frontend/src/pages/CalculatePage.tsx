import { useMutation } from '@tanstack/react-query';
import { useState } from 'react';
import { api, unwrap } from '@/api/client';
import { useDrugs } from '@/api/hooks';
import { CalcForm } from '@/components/calc/CalcForm';
import { EMPTY_VALUES, toRequest, type CalcFormValues } from '@/components/calc/formValues';
import { ResultPanel, type CalcResult } from '@/components/calc/ResultPanel';
import { Skeleton } from '@/components/ui/primitives';
import { t } from '@/i18n';
import { fieldErrorsOf, notifyError } from '@/lib/notify';

export function CalculatePage() {
  const drugs = useDrugs();
  const [result, setResult] = useState<CalcResult | null>(null);
  const [decided, setDecided] = useState(false);
  const [serverErrors, setServerErrors] = useState<Record<string, string>>({});

  const calc = useMutation({
    mutationFn: (v: CalcFormValues) => unwrap(api.POST('/calculate', { body: toRequest(v) })),
    onMutate: () => {
      setResult(null);
      setDecided(false);
      setServerErrors({});
    },
    onSuccess: setResult,
    onError: (err) => {
      setServerErrors(fieldErrorsOf(err)); // подсветка полей, на которые пожаловался сервер
      notifyError(err);
    },
  });

  return (
    <div>
      <h1 className="mb-4 text-2xl font-semibold">{t('calc.title')}</h1>
      <div className="grid gap-6 lg:grid-cols-2">
        <section aria-label={t('calc.form')}>
          {drugs.isLoading ? (
            <div role="status" aria-busy="true" className="space-y-3">
              <Skeleton className="h-10" /><Skeleton className="h-10" /><Skeleton className="h-10" />
            </div>
          ) : drugs.isError ? (
            <p role="alert" className="text-destructive">{t('calc.drugs.error')}</p>
          ) : drugs.data && drugs.data.length === 0 ? (
            <p className="rounded-md bg-warning p-3 text-warning-foreground">{t('calc.drugs.empty')}</p>
          ) : (
            <CalcForm drugs={drugs.data ?? []} initial={EMPTY_VALUES} showPatientRef
              serverErrors={serverErrors} submitting={calc.isPending} onSubmit={(v) => calc.mutate(v)} />
          )}
        </section>
        <section aria-label={t('result.section')}>
          <ResultPanel result={result} loading={calc.isPending} demo={false} decided={decided}
            onDecided={() => setDecided(true)} />
        </section>
      </div>
    </div>
  );
}
