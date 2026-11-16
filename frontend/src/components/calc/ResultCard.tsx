import type { Schemas } from '@/api/client';
import { Button } from '@/components/ui/button';
import { Badge, Card } from '@/components/ui/primitives';
import { t } from '@/i18n';
import { formatNumber } from '@/lib/utils';

type Rec = Schemas['Recommendation'];

interface Props {
  rec: Rec;
  /** В demo нет аудита: кнопки решений и audit-ID скрываются. */
  demo: boolean;
  decided: boolean;
  onDecide: () => void;
}

function dosePhrase(d: Rec['dose']): string {
  const amount = `${formatNumber(d.amount_mg, 0)} ${t('unit.mg')}`;
  return d.frequency_hours === null
    ? t('result.dose.single', { amount })
    : t('result.dose.every', { amount, hours: d.frequency_hours });
}

export function ResultCard({ rec, demo, decided, onDecide }: Props) {
  const { weight, renal_function: renal, dose } = rec;
  return (
    <Card aria-live="polite" data-testid="result-recommendation" className="space-y-4">
      <div>
        <p className="text-sm text-muted-foreground">{t('result.recommended')}</p>
        <p className="text-3xl font-bold" data-testid="dose-phrase">{dosePhrase(dose)}</p>
        {dose.infusion_duration_min !== null && (
          <p className="text-sm text-muted-foreground">
            {t('result.infusion', { min: dose.infusion_duration_min })}
          </p>
        )}
        {dose.loading_dose_mg !== null && (
          <p className="mt-1 text-sm font-medium">
            {t('result.loading', { amount: formatNumber(dose.loading_dose_mg, 0) })}
          </p>
        )}
      </div>

      {rec.tdm_required && <Badge tone="warning">{t('result.tdm')}</Badge>}
      {dose.capped_by_max_daily && <Badge tone="warning">{t('result.capped')}</Badge>}

      <section aria-labelledby="rationale-h">
        <h3 id="rationale-h" className="mb-2 font-semibold">{t('result.rationale')}</h3>
        <dl className="grid grid-cols-[auto,1fr] gap-x-4 gap-y-1 text-sm">
          <dt className="text-muted-foreground">{t('result.formula')}</dt>
          <dd>{rec.formula.name}</dd>
          {weight && (
            <>
              <dt className="text-muted-foreground">{t('result.weight')}</dt>
              <dd>
                {t('result.weight.value', {
                  type: weight.type, used: formatNumber(weight.used_kg),
                })}
                {weight.tbw_kg !== null && weight.ibw_kg !== null && weight.bmi !== null && (
                  <span className="text-muted-foreground">
                    {' '}
                    {t('result.weight.detail', {
                      tbw: formatNumber(weight.tbw_kg), ibw: formatNumber(weight.ibw_kg), bmi: formatNumber(weight.bmi),
                    })}
                  </span>
                )}
              </dd>
            </>
          )}
          {renal && (
            <>
              <dt className="text-muted-foreground">{t('result.renal')}</dt>
              <dd>{formatNumber(renal.value)} {renal.unit === 'mL/min' ? t('unit.mlmin') : renal.unit}</dd>
            </>
          )}
          <dt className="text-muted-foreground">{t('result.source')}</dt>
          <dd>{t('result.source.value', { source: rec.formula.source, version: rec.rule_version })}</dd>
        </dl>
      </section>

      {rec.warnings.length > 0 && (
        <ul className="list-disc space-y-1 pl-5 text-sm">
          {rec.warnings.map((w) => <li key={w}>{w}</li>)}
        </ul>
      )}

      {!demo && (
        <div className="flex flex-wrap gap-2 border-t border-border pt-4">
          {decided ? (
            <Badge tone="success">{t('decision.saved')}</Badge>
          ) : (
            <Button onClick={onDecide}>{t('decision.open')}</Button>
          )}
        </div>
      )}
      {!demo && (
        <p className="text-xs text-muted-foreground" data-testid="audit-id">
          {t('result.audit', { id: rec.audit_id })}
        </p>
      )}
      {demo && <p className="text-xs text-muted-foreground">{t('result.demo.note')}</p>}
    </Card>
  );
}
