import { toast } from 'sonner';
import type { Schemas } from '@/api/client';
import { Button } from '@/components/ui/button';
import { t, tDynamic } from '@/i18n';

interface Props {
  result: Schemas['FailSafeResponse'];
  demo: boolean;
  decided: boolean;
  onDecide: () => void;
}

/**
 * Fail-safe — не ошибка, а штатный клинический исход (ТЗ 7.9): крупный красный блок, не toast.
 * Причина берётся из справочника переводов по коду; нет перевода — показываем текст сервера.
 */
export function FailSafeBlock({ result, demo, decided, onDecide }: Props) {
  const display = tDynamic('failsafe', result.no_recommendation_reason);
  const title = display === result.no_recommendation_reason ? result.no_recommendation_display : display;

  // Эскалации в пилоте нет (нет бэкенда уведомлений): честно сообщаем об этом, а не имитируем отправку.
  const callPharmacist = () => toast.info(t('failsafe.call.stub'), { duration: 8000 });

  return (
    <section
      role="alert"
      data-testid="result-failsafe"
      aria-labelledby="failsafe-h"
      className="space-y-3 rounded-lg border-2 border-destructive bg-destructive/10 p-5"
    >
      <h2 id="failsafe-h" className="text-2xl font-bold text-destructive">
        <span aria-hidden="true">⚠ </span>
        {t('failsafe.title')}
      </h2>
      <p className="text-lg font-semibold">{title}</p>
      <p className="text-sm">{result.details}</p>
      <div className="flex flex-wrap gap-2 pt-2">
        <Button variant="destructive" onClick={callPharmacist}>{t('failsafe.call')}</Button>
        {!demo && !decided && (
          <Button variant="outline" onClick={onDecide}>{t('failsafe.record')}</Button>
        )}
        {!demo && decided && <span className="self-center text-sm font-medium">{t('decision.saved')}</span>}
      </div>
      {!demo && (
        <p className="text-xs text-muted-foreground" data-testid="audit-id">
          {t('result.audit', { id: result.audit_id })}
        </p>
      )}
    </section>
  );
}
