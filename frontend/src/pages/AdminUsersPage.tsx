import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { api, unwrap, type Schemas } from '@/api/client';
import { useAuth } from '@/auth/AuthContext';
import { ASSIGNABLE_ROLES, InviteDialog } from '@/components/admin/InviteDialog';
import { Button } from '@/components/ui/button';
import { Badge, Card, Select, Skeleton } from '@/components/ui/primitives';
import { t, tDynamic } from '@/i18n';
import { notifyError, notifySuccess } from '@/lib/notify';

export function AdminUsersPage() {
  const { user: me } = useAuth();
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [invited, setInvited] = useState<Schemas['UserInvited'] | null>(null);

  const q = useQuery({ queryKey: ['admin', 'users'], queryFn: () => unwrap(api.GET('/admin/users')) });
  const refresh = () => qc.invalidateQueries({ queryKey: ['admin', 'users'] });

  const patch = useMutation({
    mutationFn: (a: { id: number; body: Schemas['UserPatch'] }) =>
      unwrap(api.PATCH('/admin/users/{user_id}', { params: { path: { user_id: a.id } }, body: a.body })),
    onSuccess: () => { notifySuccess(t('users.saved')); void refresh(); },
    onError: (e) => { notifyError(e); void refresh(); }, // возвращаем select к серверному значению
  });

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">{t('users.title')}</h1>
        <Button onClick={() => setOpen(true)}>{t('users.invite')}</Button>
      </div>

      {invited && (
        <div role="status" className="space-y-1 rounded-lg border-2 border-primary bg-card p-4" data-testid="invited">
          <p className="font-semibold">{t('users.invited', { email: invited.email })}</p>
          <p className="text-sm">
            {t('users.temp')}{' '}
            <code className="rounded bg-muted px-1.5 py-0.5 font-mono">{invited.temp_password}</code>
          </p>
          <p className="text-xs text-muted-foreground">{t('users.temp.once')}</p>
          <Button size="sm" variant="outline" onClick={() => setInvited(null)}>{t('common.close')}</Button>
        </div>
      )}

      <Card className="overflow-x-auto p-0">
        <table className="w-full text-left text-sm">
          <caption className="sr-only">{t('users.title')}</caption>
          <thead className="bg-muted">
            <tr>
              {(['name', 'email', 'role', 'status'] as const).map((c) => (
                <th key={c} scope="col" className="px-3 py-2 font-semibold">{t(`users.col.${c}`)}</th>
              ))}
              <th scope="col" className="px-3 py-2"><span className="sr-only">{t('common.actions')}</span></th>
            </tr>
          </thead>
          <tbody>
            {q.isLoading && [0, 1, 2].map((i) => (
              <tr key={i}><td colSpan={5} className="px-3 py-2"><Skeleton className="h-6" /></td></tr>
            ))}
            {q.data?.map((u) => {
              const self = u.id === me?.id;
              const roles = u.role === 'super_admin' ? [...ASSIGNABLE_ROLES, 'super_admin' as const] : ASSIGNABLE_ROLES;
              return (
                <tr key={u.id} className="border-t border-border">
                  <td className="px-3 py-2">{u.full_name}{self && ` (${t('users.you')})`}</td>
                  <td className="px-3 py-2">{u.email}</td>
                  <td className="px-3 py-2">
                    <label className="sr-only" htmlFor={`role-${u.id}`}>{t('users.col.role')}: {u.full_name}</label>
                    <Select id={`role-${u.id}`} className="h-8 w-auto" value={u.role} disabled={self}
                      onChange={(e) => patch.mutate({ id: u.id, body: { role: e.target.value as Schemas['UserPatch']['role'] } })}>
                      {roles.map((r) => <option key={r} value={r}>{tDynamic('role', r)}</option>)}
                    </Select>
                  </td>
                  <td className="px-3 py-2">
                    <Badge tone={u.is_active ? 'success' : 'neutral'}>
                      {u.is_active ? t('users.active') : t('users.inactive')}
                    </Badge>
                    {u.must_change_password && <Badge tone="warning" className="ml-1">{t('users.mustchange')}</Badge>}
                  </td>
                  <td className="px-3 py-2 text-right">
                    {!self && (
                      <Button size="sm" variant="outline"
                        onClick={() => patch.mutate({ id: u.id, body: { is_active: !u.is_active } })}>
                        {u.is_active ? t('users.deactivate') : t('users.activate')}
                      </Button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {q.isError && <p role="alert" className="p-6 text-destructive">{t('users.error')}</p>}
      </Card>

      <InviteDialog open={open} onOpenChange={setOpen} onInvited={(u) => { setInvited(u); void refresh(); }} />
    </div>
  );
}
