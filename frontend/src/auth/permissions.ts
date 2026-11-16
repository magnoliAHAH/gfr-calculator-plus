/** Матрица доступа к экранам (ТЗ 7.1) и действиям (ТЗ 3.2). Бэкенд проверяет права независимо. */
export type Role = 'super_admin' | 'org_admin' | 'pharmacist' | 'physician' | 'auditor';

export const CALCULATE_ROLES: Role[] = ['super_admin', 'org_admin', 'pharmacist', 'physician'];
export const AUDIT_ROLES: Role[] = ['super_admin', 'org_admin', 'pharmacist', 'auditor'];
export const DRUGS_ROLES: Role[] = ['super_admin', 'org_admin', 'pharmacist'];
export const USERS_ROLES: Role[] = ['super_admin', 'org_admin'];
export const DASHBOARD_ROLES: Role[] = ['super_admin', 'org_admin', 'pharmacist', 'auditor'];
export const DRUG_EDIT_ROLES: Role[] = ['super_admin', 'org_admin'];

export function can(role: Role | undefined, allowed: Role[]): boolean {
  return role !== undefined && allowed.includes(role);
}

/** Куда вести пользователя после входа. */
export function homeFor(role: Role): string {
  if (can(role, CALCULATE_ROLES)) return '/calculate';
  return '/audit';
}
