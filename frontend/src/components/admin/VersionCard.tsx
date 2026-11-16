import type { Schemas } from '@/api/client';
import { Badge, Card } from '@/components/ui/primitives';
import { t, tDynamic } from '@/i18n';
import { formatDateTime } from '@/lib/utils';

type Rule = Schemas['RuleOut'];

function bracketLabel(r: Rule): string {
  return r.rrt_mode !== 'none' ? `RRT ${r.rrt_mode}` : `${r.min_crcl}–${r.max_crcl}`;
}

function doseLabel(r: Rule): string {
  const base = r.dose_per_kg !== null ? `${r.dose_per_kg} ${t('unit.mgkg')}` : `${r.dose_mg} ${t('unit.mg')}`;
  return r.frequency_hours === null ? `${base}, ${t('rules.single')}` : `${base} / ${r.frequency_hours} ${t('unit.h')}`;
}

/** Одна версия правил показания; активная выделена рамкой (ТЗ 7.6). */
export function VersionCard({ group }: { group: Schemas['RuleVersionGroup'] }) {
  return (
    <Card className={group.is_active ? 'border-2 border-primary' : 'opacity-80'} data-testid={`version-${group.version}`}>
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <h3 className="font-semibold">{t('rules.version', { n: group.version })}</h3>
        <Badge tone={group.is_active ? 'success' : 'neutral'}>
          {group.is_active ? t('rules.active') : t('rules.retired')}
        </Badge>
        {group.retired_at && <span className="text-xs text-muted-foreground">{formatDateTime(group.retired_at)}</span>}
        <span className="text-xs text-muted-foreground">{group.rules[0]?.source}</span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <caption className="sr-only">{`${group.indication}, ${t('rules.version', { n: group.version })}`}</caption>
          <thead>
            <tr>
              {(['crcl', 'dose', 'weight', 'tdm'] as const).map((c) => (
                <th key={c} scope="col" className="px-2 py-1 font-semibold">{t(`rules.th.${c}`)}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {group.rules.map((r) => (
              <tr key={r.id} className="border-t border-border">
                <td className="px-2 py-1">{bracketLabel(r)}</td>
                <td className="px-2 py-1">{doseLabel(r)}</td>
                <td className="px-2 py-1">{tDynamic('weightrule', r.weight_rule)}</td>
                <td className="px-2 py-1">{r.tdm_required ? t('common.yes') : t('common.no')}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
