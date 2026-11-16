import { useQueryClient } from '@tanstack/react-query';
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { api, setUnauthorizedHandler, tokenStore, unwrap, unwrapEmpty, type Schemas } from '@/api/client';

export type User = Schemas['UserOut'];

interface AuthState {
  user: User | null;
  /** true, пока идёт восстановление сессии по сохранённому токену */
  loading: boolean;
  login: (email: string, password: string) => Promise<User>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState<boolean>(tokenStore.get() !== null);
  const queryClient = useQueryClient();

  const reset = useCallback(() => {
    tokenStore.clear();
    setUser(null);
    queryClient.clear(); // данные прошлого пользователя не должны остаться в кэше
  }, [queryClient]);

  useEffect(() => {
    setUnauthorizedHandler(reset);
  }, [reset]);

  useEffect(() => {
    if (!tokenStore.get()) return;
    unwrap(api.GET('/auth/me'), { skipUnauthorizedHandler: true })
      .then(setUser)
      .catch(() => reset())
      .finally(() => setLoading(false));
  }, [reset]);

  const login = useCallback(async (email: string, password: string) => {
    const res = await unwrap(api.POST('/auth/login', { body: { email, password } }), {
      skipUnauthorizedHandler: true,
    });
    tokenStore.set(res.access_token);
    setUser(res.user);
    return res.user;
  }, []);

  const logout = useCallback(async () => {
    try {
      await unwrapEmpty(api.POST('/auth/logout'), { skipUnauthorizedHandler: true });
    } catch {
      // токен без состояния: даже если запрос не дошёл, локальный выход всё равно выполняем
    }
    reset();
  }, [reset]);

  const refresh = useCallback(async () => {
    setUser(await unwrap(api.GET('/auth/me')));
  }, []);

  const value = useMemo(() => ({ user, loading, login, logout, refresh }), [user, loading, login, logout, refresh]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider');
  return ctx;
}
