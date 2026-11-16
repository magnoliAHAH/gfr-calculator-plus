import { useMutation } from '@tanstack/react-query';
import { useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { api, unwrap } from '@/api/client';
import { useDemoDrugs, useDemoScenarios } from '@/api/hooks';
import { CalcForm } from '@/components/calc/CalcForm';
import {
  EMPTY_VALUES, toDemoRequest, valuesFromScenario, type CalcFormValues,
} from '@/components/calc/formValues';
import { ResultPanel, type CalcResult } from '@/components/calc/ResultPanel';
import { Button } from '@/components/ui/button';
import { Card, Skeleton } from '@/components/ui/primitives';
import { t } from '@/i18n';
import { notifyError } from '@/lib/notify';

/** Публичный demo (ТЗ 4.7): без входа, без аудита, данные берутся с демо-эндпоинтов. */
export function DemoPage() {
  const scenarios = useDemoScenarios();
  const drugs = useDemoDrugs();
  const [initial, setInitial] = useState<CalcFormValues>(EMPTY_VALUES);
  const [result, setResult] = useState<CalcResult | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const formRef = useRef<HTMLDivElement>(null);

  const indications = useMemo(
    () => Object.fromEntries((drugs.data ?? []).map((d) => [d.drug_code, d.indications])),
    [drugs.data],
  );

  const calc = useMutation({
    mutationFn: (v: CalcFormValues) => unwrap(api.POST('/demo/calculate', { body: toDemoRequest(v) })),
    onMutate: () => setResult(null),
    onSuccess: setResult,
    onError: notifyError,
  });

  const pick = (s: NonNullable<typeof scenarios.data>[number]) => {
    setInitial(valuesFromScenario(s.request));
    setMessage(s.message);
    setResult(null);
    formRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  return (
    <main className="mx-auto max-w-7xl space-y-6 px-4 py-6">
      <header className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-2xl font-semibold">{t('demo.title')}</h1>
          <p className="text-sm text-muted-foreground">{t('demo.subtitle')}</p>
        </div>
        <Button asChild variant="outline"><Link to="/login">{t('demo.login')}</Link></Button>
      </header>

      <section aria-label={t('demo.scenarios')}>
        <ul className="grid gap-4 md:grid-cols-3">
          {scenarios.isLoading && [0, 1, 2].map((i) => <li key={i}><Skeleton className="h-40" /></li>)}
          {scenarios.data?.map((s) => (
            <li key={s.id}>
              <Card className="flex h-full flex-col gap-2" data-testid={`scenario-${s.id}`}>
                <h2 className="font-semibold">{s.title}</h2>
                <p className="flex-1 text-sm">{s.description}</p>
                <Button onClick={() => pick(s)} aria-label={t('demo.try', { title: s.title })}>
                  {t('demo.fill')}
                </Button>
              </Card>
            </li>
          ))}
        </ul>
        {scenarios.isError && <p role="alert" className="text-destructive">{t('demo.error')}</p>}
      </section>

      <div ref={formRef} className="grid scroll-mt-4 gap-6 lg:grid-cols-2">
        <section aria-label={t('calc.form')}>
          {drugs.isLoading ? <Skeleton className="h-96" /> : (
            <CalcForm drugs={drugs.data ?? []} demoIndications={indications} initial={initial}
              showPatientRef={false} submitting={calc.isPending} onSubmit={(v) => calc.mutate(v)} />
          )}
        </section>
        <section aria-label={t('result.section')} className="space-y-4">
          <ResultPanel result={result} loading={calc.isPending} demo decided={false} onDecided={() => undefined} />
          {message && result && (
            <Card className="border-primary" data-testid="demo-message">
              <p className="text-sm font-semibold">{t('demo.shows')}</p>
              <p>{message}</p>
            </Card>
          )}
        </section>
      </div>
    </main>
  );
}
