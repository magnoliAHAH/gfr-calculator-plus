import { useQuery } from '@tanstack/react-query';
import { api, unwrap } from '@/api/client';
import { Badge, Skeleton } from '@/components/ui/primitives';
import { t } from '@/i18n';

/** Бейдж целостности всей цепочки организации (ТЗ 4.3.3, 7.3). */
export function ChainBadge({ refreshKey }: { refreshKey?: unknown }) {
  const q = useQuery({
    queryKey: ['audit', 'chain', refreshKey],
    queryFn: () => unwrap(api.GET('/audit/chain/verify')),
  });
  if (q.isLoading) return <Skeleton className="h-6 w-56" />;
  if (q.isError || !q.data) return <Badge tone="warning">{t('chain.unknown')}</Badge>;
  const v = q.data;
  return v.valid ? (
    <Badge tone="success" data-testid="chain-badge">
      {t('chain.ok', { n: v.total_records_checked })}
    </Badge>
  ) : (
    <Badge tone="danger" data-testid="chain-badge">
      {t('chain.broken', { id: v.first_invalid_id ?? '?' })}
    </Badge>
  );
}
