import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '@/auth/AuthContext';
import { can, homeFor, type Role } from '@/auth/permissions';
import { Skeleton } from '@/components/ui/primitives';

/**
 * Без `roles` — только проверка входа (и принудительная смена временного пароля).
 * С `roles` — ещё и роль; чужой роли показываем домашний экран, а не пустую страницу.
 * Это удобство интерфейса: настоящие права проверяет бэкенд.
 */
export function RequireAuth({ roles }: { roles?: Role[] }) {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) {
    return (
      <div className="p-8" role="status" aria-busy="true">
        <Skeleton className="h-8 w-64" />
      </div>
    );
  }
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  if (user.must_change_password && location.pathname !== '/change-password') {
    return <Navigate to="/change-password" replace />;
  }
  if (roles && !can(user.role, roles)) return <Navigate to={homeFor(user.role)} replace />;
  return <Outlet />;
}
