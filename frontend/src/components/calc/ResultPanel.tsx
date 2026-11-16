import { useState } from 'react';
import type { Schemas } from '@/api/client';
import { Skeleton } from '@/components/ui/primitives';
import { t } from '@/i18n';
import { DecisionDialog } from './DecisionDialog';
import { FailSafeBlock } from './FailSafeBlock';
import { ResultCard } from './ResultCard';

export type CalcResult = Schemas['Recommendation'] | Schemas['FailSafeResponse'];

interface Props {
  result: CalcResult | null;
  loading: boolean;
  demo: boolean;
  /** Решение уже сохранено для этого результата */
  decided: boolean;
  onDecided: () => void;
}

/** Правая колонка /calculate и /demo: скелетон -> рекомендация | fail-safe | пустое состояние. */
export function ResultPanel({ result, loading, demo, decided, onDecided }: Props) {
  const [open, setOpen] = useState(false);

  if (loading) {
    return (
      <div role="status" aria-busy="true" aria-label={t('common.loading')} className="space-y-3">
        <Skeleton className="h-10 w-3/4" />
        <Skeleton className="h-6 w-1/3" />
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-10 w-1/2" />
      </div>
    );
  }
  if (!result) {
    return (
      <div className="rounded-lg border border-dashed border-border p-8 text-center text-muted-foreground">
        {t('result.empty')}
      </div>
    );
  }

  const failSafe = result.calculation_mode === 'blocked_fail_safe';
  return (
    <>
      {result.calculation_mode === 'blocked_fail_safe' ? (
        <FailSafeBlock result={result} demo={demo} decided={decided} onDecide={() => setOpen(true)} />
      ) : (
        <ResultCard rec={result} demo={demo} decided={decided} onDecide={() => setOpen(true)} />
      )}
      {!demo && (
        <DecisionDialog open={open} onOpenChange={setOpen} auditId={result.audit_id}
          allowAccept={!failSafe} onSaved={onDecided} />
      )}
    </>
  );
}
