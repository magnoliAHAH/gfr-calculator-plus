import { t } from '@/i18n';

export interface BarDatum {
  label: string;
  value: number;
  /** Подпись справа от столбца (например, «3 · 60%») */
  note?: string;
}

interface Props {
  title: string;
  data: BarDatum[];
  /** Вертикальные столбцы (гистограмма) или горизонтальные (топы) */
  orientation?: 'horizontal' | 'vertical';
}

/**
 * Простая диаграмма на div'ах: без внешней библиотеки. Доступность: заголовок + таблица
 * для скринридера (визуальная часть скрыта через aria-hidden, данные дублируются в <table>).
 */
export function BarChart({ title, data, orientation = 'horizontal' }: Props) {
  const max = Math.max(1, ...data.map((d) => d.value));
  const empty = data.every((d) => d.value === 0);

  return (
    <figure aria-label={title} className="space-y-2">
      <figcaption className="font-semibold">{title}</figcaption>
      {empty ? (
        <p className="text-sm text-muted-foreground">{t('dashboard.nodata')}</p>
      ) : orientation === 'horizontal' ? (
        <ul aria-hidden="true" className="space-y-1.5">
          {data.map((d) => (
            <li key={d.label} className="grid grid-cols-[8rem,1fr,auto] items-center gap-2 text-sm">
              <span className="truncate">{d.label}</span>
              <span className="h-4 rounded bg-muted">
                <span className="block h-4 rounded bg-primary" style={{ width: `${(d.value / max) * 100}%` }} />
              </span>
              <span className="text-xs text-muted-foreground">{d.note ?? d.value}</span>
            </li>
          ))}
        </ul>
      ) : (
        <div aria-hidden="true" className="flex h-40 items-end gap-2">
          {data.map((d) => (
            <div key={d.label} className="flex flex-1 flex-col items-center justify-end gap-1">
              <span className="text-xs text-muted-foreground">{d.value}</span>
              <div className="w-full rounded-t bg-primary" style={{ height: `${(d.value / max) * 100}%`, minHeight: d.value > 0 ? 2 : 0 }} />
              <span className="text-xs">{d.label}</span>
            </div>
          ))}
        </div>
      )}
      <table className="sr-only">
        <caption>{title}</caption>
        <tbody>
          {data.map((d) => (
            <tr key={d.label}><th scope="row">{d.label}</th><td>{d.value}</td></tr>
          ))}
        </tbody>
      </table>
    </figure>
  );
}
