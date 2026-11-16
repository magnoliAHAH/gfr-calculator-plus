import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { api, unwrap } from '@/api/client';
import { useAuth } from '@/auth/AuthContext';
import { can, DASHBOARD_ROLES } from '@/auth/permissions';
import { AuditFilters, EMPTY_FILTERS, type Filters } from '@/components/audit/AuditFilters';
import { AuditTable } from '@/components/audit/AuditTable';
import { ChainBadge } from '@/components/audit/ChainBadge';
import { Button } from '@/components/ui/button';
import { t } from '@/i18n';

const LIMIT = 20;

/** Дата из <input type="date"> -> начало суток локального времени в ISO (UTC). */
function dayStart(d: string, addDays = 0): string | undefined {
  if (!d) return undefined;
  const date = new Date(`${d}T00:00:00`);
  date.setDate(date.getDate() + addDays);
  return date.toISOString();
}

export function AuditListPage() {
  const { user } = useAuth();
  const [filters, setFilters] = useState<Filters>(EMPTY_FILTERS);
  const [page, setPage] = useState(1);

  const q = useQuery({
    queryKey: ['audit', 'list', filters, page],
    queryFn: () => unwrap(api.GET('/audit', {
      params: { query: {
        from: dayStart(filters.from), to: dayStart(filters.to, 1), // «по» включает весь выбранный день
        drug: filters.drug || undefined, decision: filters.decision || undefined,
        patient_ref: filters.patient_ref.trim() || undefined, page, limit: LIMIT,
      } },
    })),
    placeholderData: (prev) => prev,
  });

  const totalPages = q.data ? Math.max(1, Math.ceil(q.data.total / LIMIT)) : 1;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-2xl font-semibold">{t('audit.title')}</h1>
        {can(user?.role, DASHBOARD_ROLES) && <ChainBadge />}
      </div>

      <AuditFilters onApply={(f) => { setFilters(f); setPage(1); }} />
      <AuditTable items={q.data?.items} loading={q.isLoading} error={q.isError} />

      <nav className="flex items-center justify-between" aria-label={t('audit.pagination')}>
        <span className="text-sm text-muted-foreground">
          {t('audit.total', { n: q.data?.total ?? 0 })} · {t('audit.page', { page, pages: totalPages })}
        </span>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
            {t('audit.prev')}
          </Button>
          <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>
            {t('audit.next')}
          </Button>
        </div>
      </nav>
    </div>
  );
}
