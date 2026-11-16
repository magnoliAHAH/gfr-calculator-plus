import { Link } from 'react-router-dom';
import type { Schemas } from '@/api/client';
import { Badge, Card, Skeleton } from '@/components/ui/primitives';
import { t, tDynamic } from '@/i18n';
import { formatDateTime, formatNumber } from '@/lib/utils';

const COLS = ['date', 'patient', 'drug', 'crcl', 'mode', 'decision', 'doctor', 'hash'] as const;

function crclOf(e: Schemas['AuditEntry']): string {
  const renal = (e.recommended_dose as { renal_function?: { value?: number } } | null)?.renal_function;
  return renal?.value !== undefined ? formatNumber(renal.value) : '—';
}

interface Props {
  items: Schemas['AuditEntry'][] | undefined;
  loading: boolean;
  error: boolean;
}

export function AuditTable({ items, loading, error }: Props) {
  return (
    <Card className="overflow-x-auto p-0">
      <table className="w-full text-left text-sm">
        <caption className="sr-only">{t('audit.title')}</caption>
        <thead className="bg-muted">
          <tr>
            {COLS.map((c) => (
              <th key={c} scope="col" className="px-3 py-2 font-semibold">{t(`audit.col.${c}`)}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {loading && [0, 1, 2, 3, 4].map((i) => (
            <tr key={i}><td colSpan={COLS.length} className="px-3 py-2"><Skeleton className="h-6" /></td></tr>
          ))}
          {items?.map((e) => (
            <tr key={e.id} className="border-t border-border hover:bg-muted/50">
              <td className="px-3 py-2">
                <Link to={`/audit/${e.id}`} className="text-primary underline">{formatDateTime(e.created_at)}</Link>
              </td>
              <td className="px-3 py-2">{e.patient_ref}</td>
              <td className="px-3 py-2">{e.drug?.name as string | undefined ?? '—'}</td>
              <td className="px-3 py-2">{crclOf(e)}</td>
              <td className="px-3 py-2">
                <Badge tone={e.calculation_mode === 'blocked_fail_safe' ? 'danger' : 'neutral'}>
                  {tDynamic('mode', e.calculation_mode)}
                </Badge>
              </td>
              <td className="px-3 py-2">{tDynamic('decision', e.doctor_decision)}</td>
              <td className="px-3 py-2">{e.user.full_name as string}</td>
              <td className="px-3 py-2 font-mono text-xs">{e.record_hash.slice(0, 8)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {items && items.length === 0 && <p className="p-6 text-center text-muted-foreground">{t('audit.empty')}</p>}
      {error && <p role="alert" className="p-6 text-destructive">{t('audit.error')}</p>}
    </Card>
  );
}
