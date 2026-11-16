import { NavLink, Outlet } from 'react-router-dom';
import { useAuth } from '@/auth/AuthContext';
import {
  AUDIT_ROLES, CALCULATE_ROLES, DASHBOARD_ROLES, DRUGS_ROLES, USERS_ROLES, can,
} from '@/auth/permissions';
import { Button } from '@/components/ui/button';
import { t, tDynamic } from '@/i18n';
import { cn } from '@/lib/utils';

export function Layout() {
  const { user, logout } = useAuth();
  if (!user) return null;

  const links = [
    { to: '/calculate', label: t('nav.calculate'), show: can(user.role, CALCULATE_ROLES) },
    { to: '/audit', label: t('nav.audit'), show: can(user.role, AUDIT_ROLES) },
    { to: '/dashboard', label: t('nav.dashboard'), show: can(user.role, DASHBOARD_ROLES) },
    { to: '/admin/drugs', label: t('nav.drugs'), show: can(user.role, DRUGS_ROLES) },
    { to: '/admin/users', label: t('nav.users'), show: can(user.role, USERS_ROLES) },
    { to: '/demo', label: t('nav.demo'), show: true },
  ].filter((l) => l.show);

  return (
    <div className="min-h-screen">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded focus:bg-card focus:p-2">
        {t('nav.skip')}
      </a>
      <header className="border-b border-border bg-card">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3">
          <span className="font-semibold">{t('app.title')}</span>
          <nav aria-label={t('nav.main')} className="flex flex-wrap gap-1">
            {links.map((l) => (
              <NavLink
                key={l.to}
                to={l.to}
                className={({ isActive }) =>
                  cn('rounded-md px-3 py-1.5 text-sm hover:bg-muted', isActive && 'bg-muted font-semibold')
                }
              >
                {l.label}
              </NavLink>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-3 text-sm">
            <span>
              <span className="font-medium">{user.full_name}</span>
              <span className="text-muted-foreground">
                {' · '}
                {tDynamic('role', user.role)}
                {' · '}
                {user.organization_name}
              </span>
            </span>
            <Button variant="outline" size="sm" onClick={() => void logout()}>
              {t('nav.logout')}
            </Button>
          </div>
        </div>
      </header>
      <main id="main" className="mx-auto max-w-7xl px-4 py-6">
        <Outlet />
      </main>
    </div>
  );
}
