import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { api, downloadFile, unwrap } from '@/api/client';
import { ChainBadge } from '@/components/audit/ChainBadge';
import { BarChart } from '@/components/dashboard/BarChart';
import { Button } from '@/components/ui/button';
import { Card, Skeleton } from '@/components/ui/primitives';
import { t, tDynamic } from '@/i18n';
import { notifyError } from '@/lib/notify';
import { formatNumber } from '@/lib/utils';

const PERIODS = [7, 30, 90] as const;
type Period = (typeof PERIODS)[number];

function range(days: Period): { from: string; to: string } {
  const to = new Date();
  return { from: new Date(to.getTime() - days * 86_400_000).toISOString(), to: to.toISOString() };
}

function Stat({ label, value, sub, testId }: { label: string; value: string; sub?: string; testId: string }) {
  return (
    <Card data-testid={testId}>
      <p className="text-sm text-muted-foreground">{label}</p>
      <p className="text-3xl font-bold">{value}</p>
      {sub && <p className="text-xs text-muted-foreground">{sub}</p>}
    </Card>
  );
}

export function DashboardPage() {
  const [days, setDays] = useState<Period>(30);
  const q = useQuery({
    queryKey: ['dashboard', days],
    queryFn: () => unwrap(api.GET('/dashboard/metrics', { params: { query: range(days) } })),
  });
  const m = q.data;

  const exportCsv = () => {
    const r = range(days);
    void downloadFile(`/dashboard/export?from=${encodeURIComponent(r.from)}&to=${encodeURIComponent(r.to)}`,
      `dashboard-${days}d.csv`).catch(notifyError);
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-2xl font-semibold">{t('dashboard.title')}</h1>
        <div className="flex flex-wrap items-center gap-2">
          <div role="tablist" aria-label={t('dashboard.period')} className="flex rounded-md border border-border">
            {PERIODS.map((p) => (
              <button key={p} role="tab" type="button" aria-selected={days === p} onClick={() => setDays(p)}
                className={`px-3 py-1.5 text-sm ${days === p ? 'bg-primary text-primary-foreground' : 'bg-card hover:bg-muted'}`}>
                {t('dashboard.days', { n: p })}
              </button>
            ))}
          </div>
          <Button variant="outline" onClick={exportCsv}>{t('dashboard.export')}</Button>
        </div>
      </div>

      {q.isError && <p role="alert" className="text-destructive">{t('dashboard.error')}</p>}
      {q.isLoading && (
        <div role="status" aria-busy="true" className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-24" />)}
        </div>
      )}

      {m && (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Stat testId="stat-total" label={t('dashboard.total')} value={String(m.recommendations.total)}
              sub={t('dashboard.pending', { n: m.recommendations.pending })} />
            <Stat testId="stat-accepted" label={t('dashboard.accepted')} value={`${formatNumber(m.recommendations.accepted_pct)}%`}
              sub={String(m.recommendations.accepted)} />
            <Stat testId="stat-overridden" label={t('dashboard.overridden')} value={`${formatNumber(m.recommendations.overridden_pct)}%`}
              sub={`${m.recommendations.overridden} · ${t('dashboard.rejected', { n: m.recommendations.rejected })}`} />
            <Stat testId="stat-failsafe" label={t('dashboard.failsafe')} value={`${formatNumber(m.failsafe_rate)}%`} />
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <BarChart title={t('dashboard.reasons')}
                data={m.override_reasons_top.map((r) => ({
                  label: tDynamic('override', r.code), value: r.count, note: `${r.count} · ${formatNumber(r.percentage)}%`,
                }))} />
            </Card>
            <Card>
              <BarChart title={t('dashboard.drugs')} data={m.drugs_top.map((d) => ({ label: d.name, value: d.count }))} />
            </Card>
            <Card>
              <BarChart title={t('dashboard.crcl')} orientation="vertical"
                data={m.renal_function_histogram.map((b) => ({ label: b.bucket, value: b.count }))} />
            </Card>
            <Card className="space-y-3">
              <h2 className="font-semibold">{t('dashboard.integrity')}</h2>
              <ChainBadge refreshKey={days} />
              <p className="text-sm">
                {t('dashboard.perf')}: p50 {m.performance.p50_ms !== null ? `${formatNumber(m.performance.p50_ms)} ${t('unit.ms')}` : '—'}
                {' · '}
                p95 {m.performance.p95_ms !== null ? `${formatNumber(m.performance.p95_ms)} ${t('unit.ms')}` : '—'}
              </p>
            </Card>
          </div>
        </>
      )}
    </div>
  );
}
