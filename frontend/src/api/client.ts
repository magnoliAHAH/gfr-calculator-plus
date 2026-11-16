import createClient, { type Middleware } from 'openapi-fetch';
import type { components, paths } from './schema';

export type Schemas = components['schemas'];

const baseUrl = import.meta.env.VITE_API_BASE_URL ?? '/api/v1';
const TOKEN_KEY = 'cdss.token';

export const tokenStore = {
  get: (): string | null => sessionStorage.getItem(TOKEN_KEY),
  set: (token: string): void => sessionStorage.setItem(TOKEN_KEY, token),
  clear: (): void => sessionStorage.removeItem(TOKEN_KEY),
};

/** Ошибка API в формате RFC 7807 (ТЗ 6). Входные значения в ней отсутствуют (нет PHI). */
export class ApiProblem extends Error {
  constructor(
    public readonly status: number,
    public readonly title: string,
    detail: string,
    public readonly correlationId: string | null,
    public readonly fieldErrors: { field: string; message: string }[] = [],
  ) {
    super(detail);
  }
}

type UnauthorizedHandler = () => void;
let onUnauthorized: UnauthorizedHandler = () => undefined;
export function setUnauthorizedHandler(handler: UnauthorizedHandler): void {
  onUnauthorized = handler;
}

const authMiddleware: Middleware = {
  onRequest({ request }) {
    const token = tokenStore.get();
    if (token) request.headers.set('Authorization', `Bearer ${token}`);
    return request;
  },
};

export const api = createClient<paths>({ baseUrl });
api.use(authMiddleware);

interface RawProblem {
  title?: string;
  detail?: string;
  correlation_id?: string;
  errors?: { field: string; message: string }[];
}

/** Разворачивает ответ openapi-fetch: данные либо ApiProblem. 401 вне логина разлогинивает. */
export async function unwrap<T>(
  result: Promise<{ data?: T; error?: unknown; response: Response }>,
  opts: { skipUnauthorizedHandler?: boolean } = {},
): Promise<T> {
  const { data, error, response } = await result;
  if (!response.ok) {
    if (response.status === 401 && !opts.skipUnauthorizedHandler) onUnauthorized();
    const p = (error ?? {}) as RawProblem;
    throw new ApiProblem(
      response.status,
      p.title ?? 'Error',
      p.detail ?? response.statusText,
      p.correlation_id ?? response.headers.get('X-Correlation-ID'),
      p.errors ?? [],
    );
  }
  return data as T;
}

/** Для 204 No Content: данных нет, важен только статус. */
export async function unwrapEmpty(
  result: Promise<{ error?: unknown; response: Response }>,
  opts: { skipUnauthorizedHandler?: boolean } = {},
): Promise<void> {
  await unwrap(result as Promise<{ data?: unknown; error?: unknown; response: Response }>, opts);
}

/** Скачивание CSV с токеном (обычная ссылка не передаст Authorization). */
export async function downloadFile(path: string, filename: string): Promise<void> {
  const token = tokenStore.get();
  const res = await fetch(`${baseUrl}${path}`, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
  if (!res.ok) {
    if (res.status === 401) onUnauthorized();
    throw new ApiProblem(res.status, 'Error', res.statusText, res.headers.get('X-Correlation-ID'));
  }
  const url = URL.createObjectURL(await res.blob());
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

/** Загрузка CSV правил (multipart). openapi-fetch сериализует файл неудобно — используем fetch. */
export async function uploadRulesCsv(file: File): Promise<Schemas['ImportResult']> {
  const token = tokenStore.get();
  const form = new FormData();
  form.append('file', file);
  const res = await fetch(`${baseUrl}/admin/rules/import`, {
    method: 'POST',
    body: form,
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  const body = (await res.json().catch(() => ({}))) as RawProblem & Schemas['ImportResult'];
  if (!res.ok) {
    if (res.status === 401) onUnauthorized();
    const rows = (body as { errors?: { row: number; message: string }[] }).errors;
    const fieldErrors = Array.isArray(rows)
      ? rows.map((e) => ({ field: `row ${e.row}`, message: e.message }))
      : [];
    throw new ApiProblem(res.status, body.title ?? 'Error', body.detail ?? res.statusText,
      body.correlation_id ?? null, fieldErrors);
  }
  return body;
}
