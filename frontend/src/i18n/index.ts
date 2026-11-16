import ru from './ru.json';

/** Ключ обязан существовать в ru.json: опечатка — ошибка компиляции. */
export type I18nKey = keyof typeof ru;

/** Подстановка {name} в строке. Все строки интерфейса живут в ru.json (ТЗ 7.9). */
export function t(key: I18nKey, params?: Record<string, string | number>): string {
  const template = ru[key] as string;
  if (!params) return template;
  return template.replace(/\{(\w+)\}/g, (_, name: string) => String(params[name] ?? `{${name}}`));
}

/** Перевод по динамическому коду из API (причина fail-safe, роль и т.п.); нет перевода — код как есть. */
export function tDynamic(prefix: string, code: string | null | undefined): string {
  if (!code) return '—';
  const key = `${prefix}.${code}` as I18nKey;
  return key in ru ? (ru[key] as string) : code;
}
