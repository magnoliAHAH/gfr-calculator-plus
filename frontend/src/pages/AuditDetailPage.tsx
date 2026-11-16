import { useMutation, useQuery } from '@tanstack/react-query';
import { Link, useParams } from 'react-router-dom';
import { api, ApiProblem, unwrap } from '@/api/client';
import { Button } from '@/components/ui/button';
import { Badge, Card, Skeleton } from '@/components/ui/primitives';
import { t, tDynamic } from '@/i18n';
import { notifyError } from '@/lib/notify';
import { formatDateTime, formatNumber } from '@/lib/utils';

function JsonView({ title, data }: { title: string; data: unknown }) {
  return (
    <section aria-label={title}>
      <h3 className="mb-1 font-semibold">{title}</h3>
      <pre tabIndex={0} className="max-h-72 overflow-auto rounded-md bg-muted p-3 text-xs">
        {JSON.stringify(data, null, 2)}
      </pre>
    </section>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <>
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="break-words">{children}</dd>
    </>
  );
}

export function AuditDetailPage() {
  const { id } = useParams();
  const auditId = Number(id);
  const valid = Number.isInteger(auditId) && auditId > 0;

  const q = useQuery({
    queryKey: ['audit', 'detail', auditId],
    enabled: valid,
    queryFn: () => unwrap(api.GET('/audit/{audit_id}', { params: { path: { audit_id: auditId } } })),
  });

  const verify = useMutation({
    mutationFn: () => unwrap(api.GET('/audit/{audit_id}/verify', { params: { path: { audit_id: auditId } } })),
    onError: notifyError,
  });

  if (!valid || (q.error instanceof ApiProblem && q.error.status === 404)) {
    return (
      <div className="space-y-2">
        <p role="alert">{t('auditdetail.notfound')}</p>
        <Link to="/audit" className="text-primary underline">{t('auditdetail.back')}</Link>
      </div>
    );
  }
  if (q.isLoading || !q.data) {
    return (
      <div role="status" aria-busy="true" className="space-y-3">
        <Skeleton className="h-8 w-64" /><Skeleton className="h-48" />
      </div>
    );
  }

  const e = q.data;
  const rec = e.recommended_dose as {
    formula?: { name?: string; source?: string };
    weight?: { type?: string; used_kg?: number } | null;
    renal_function?: { value?: number; unit?: string } | null;
  } | null;
  const v = verify.data;

  return (
    <div className="space-y-4">
      <Link to="/audit" className="text-sm text-primary underline">{t('auditdetail.back')}</Link>
      <h1 className="text-2xl font-semibold">{t('auditdetail.title', { id: e.id })}</h1>

      <Card>
        <dl className="grid grid-cols-[auto,1fr] gap-x-6 gap-y-1 text-sm">
          <Row label={t('audit.col.date')}>{formatDateTime(e.created_at)}</Row>
          <Row label={t('audit.col.patient')}>{e.patient_ref}</Row>
          <Row label={t('audit.col.drug')}>{(e.drug?.name as string | undefined) ?? '—'}</Row>
          <Row label={t('audit.col.doctor')}>{e.user.full_name as string}</Row>
          <Row label={t('audit.col.mode')}>{tDynamic('mode', e.calculation_mode)}</Row>
          <Row label={t('result.formula')}>{rec?.formula?.name ?? '—'}</Row>
          <Row label={t('result.weight')}>
            {rec?.weight ? `${rec.weight.type} ${formatNumber(rec.weight.used_kg)} ${t('unit.kg')}` : '—'}
          </Row>
          <Row label={t('result.renal')}>
            {rec?.renal_function?.value !== undefined ? formatNumber(rec.renal_function.value) : '—'}
          </Row>
          <Row label={t('auditdetail.rule')}>
            {e.rule_id !== null ? t('auditdetail.rule.value', { id: e.rule_id ?? '', version: e.rule_version ?? '' }) : '—'}
          </Row>
          <Row label={t('audit.col.decision')}>
            <Badge tone={e.doctor_decision === 'pending' ? 'warning' : 'neutral'}>
              {tDynamic('decision', e.doctor_decision)}
            </Badge>
          </Row>
          {e.override_reason_category && (
            <Row label={t('decision.category')}>{tDynamic('override', e.override_reason_category)}</Row>
          )}
          {e.override_reason_text && <Row label={t('decision.text')}>{e.override_reason_text}</Row>}
          {e.override_new_dose_mg !== null && (
            <Row label={t('decision.newdose')}>
              {formatNumber(e.override_new_dose_mg, 0)}
              {e.override_new_frequency_hours !== null ? ` / ${e.override_new_frequency_hours} ${t('unit.h')}` : ''}
            </Row>
          )}
          {e.decision_at && <Row label={t('auditdetail.decided')}>{formatDateTime(e.decision_at)}</Row>}
          <Row label="prev_hash"><code className="break-all text-xs">{e.prev_hash}</code></Row>
          <Row label="record_hash"><code className="break-all text-xs">{e.record_hash}</code></Row>
        </dl>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <JsonView title={t('auditdetail.input')} data={e.input_data} />
        <JsonView title={t('auditdetail.output')} data={e.recommended_dose} />
      </div>

      <Card className="flex flex-wrap items-center gap-3">
        <Button onClick={() => verify.mutate()} disabled={verify.isPending}>{t('auditdetail.verify')}</Button>
        {verify.isPending && <Skeleton className="h-6 w-48" />}
        {v && (
          <div role="status" data-testid="verify-result">
            {v.valid ? (
              <Badge tone="success">{t('chain.ok', { n: v.total_records_checked })}</Badge>
            ) : (
              <Badge tone="danger">{t('chain.broken', { id: v.first_invalid_id ?? '?' })}</Badge>
            )}
          </div>
        )}
      </Card>
    </div>
  );
}
