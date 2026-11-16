import { Navigate, Route, Routes } from 'react-router-dom';
import { useAuth } from '@/auth/AuthContext';
import {
  AUDIT_ROLES, CALCULATE_ROLES, DASHBOARD_ROLES, DRUGS_ROLES, USERS_ROLES, homeFor,
} from '@/auth/permissions';
import { Layout } from '@/components/Layout';
import { RequireAuth } from '@/components/RequireAuth';
import { AdminDrugsPage } from '@/pages/AdminDrugsPage';
import { AdminRulesPage } from '@/pages/AdminRulesPage';
import { AdminUsersPage } from '@/pages/AdminUsersPage';
import { AuditDetailPage } from '@/pages/AuditDetailPage';
import { AuditListPage } from '@/pages/AuditListPage';
import { CalculatePage } from '@/pages/CalculatePage';
import { ChangePasswordPage } from '@/pages/ChangePasswordPage';
import { DashboardPage } from '@/pages/DashboardPage';
import { DemoPage } from '@/pages/DemoPage';
import { LoginPage } from '@/pages/LoginPage';
import { NotFoundPage } from '@/pages/NotFoundPage';

function HomeRedirect() {
  const { user, loading } = useAuth();
  if (loading) return null;
  return <Navigate to={user ? homeFor(user.role) : '/login'} replace />;
}

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/demo" element={<DemoPage />} />
      <Route path="/" element={<HomeRedirect />} />
      <Route element={<RequireAuth />}>
        <Route path="/change-password" element={<ChangePasswordPage />} />
        <Route element={<Layout />}>
          <Route element={<RequireAuth roles={CALCULATE_ROLES} />}>
            <Route path="/calculate" element={<CalculatePage />} />
          </Route>
          <Route element={<RequireAuth roles={AUDIT_ROLES} />}>
            <Route path="/audit" element={<AuditListPage />} />
            <Route path="/audit/:id" element={<AuditDetailPage />} />
          </Route>
          <Route element={<RequireAuth roles={DRUGS_ROLES} />}>
            <Route path="/admin/drugs" element={<AdminDrugsPage />} />
            <Route path="/admin/drugs/:id/rules" element={<AdminRulesPage />} />
          </Route>
          <Route element={<RequireAuth roles={USERS_ROLES} />}>
            <Route path="/admin/users" element={<AdminUsersPage />} />
          </Route>
          <Route element={<RequireAuth roles={DASHBOARD_ROLES} />}>
            <Route path="/dashboard" element={<DashboardPage />} />
          </Route>
        </Route>
      </Route>
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}
