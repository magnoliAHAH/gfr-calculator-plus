import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { api, unwrap, unwrapEmpty, type Schemas } from '@/api/client';
import { useAuth } from '@/auth/AuthContext';
import { can, DRUG_EDIT_ROLES } from '@/auth/permissions';
import { DrugDialog } from '@/components/admin/DrugDialog';
import { Button } from '@/components/ui/button';
import { Badge, Card, Skeleton } from '@/components/ui/primitives';
import { t } from '@/i18n';
import { notifyError, notifySuccess } from '@/lib/notify';

export function AdminDrugsPage() {
  const { user } = useAuth();
  const qc = useQueryClient();
  const canEdit = can(user?.role, DRUG_EDIT_ROLES); // pharmacist видит список и правила, но не меняет препараты
  const [showArchived, setShowArchived] = useState(false);
  const [editing, setEditing] = useState<Schemas['DrugOut'] | null>(null);
  const [open, setOpen] = useState(false);

  const q = useQuery({
    queryKey: ['admin', 'drugs'],
    queryFn: () => unwrap(api.GET('/admin/drugs', { params: { query: { include_archived: true } } })),
  });

  const archive = useMutation({
    mutationFn: (d: Schemas['DrugOut']) =>
      unwrapEmpty(api.DELETE('/admin/drugs/{drug_id}', { params: { path: { drug_id: d.id } } })),
    onSuccess: () => {
      notifySuccess(t('drugs.archived'));
      void qc.invalidateQueries({ queryKey: ['admin', 'drugs'] });
      void qc.invalidateQueries({ queryKey: ['meta', 'drugs'] });
    },
    onError: notifyError,
  });

  const items = (q.data ?? []).filter((d) => showArchived || d.is_active);
  const edit = (d: Schemas['DrugOut'] | null) => { setEditing(d); setOpen(true); };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-2xl font-semibold">{t('drugs.title')}</h1>
        <div className="flex items-center gap-4">
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={showArchived} onChange={(e) => setShowArchived(e.target.checked)} />
            {t('drugs.showarchived')}
          </label>
          {canEdit && <Button onClick={() => edit(null)}>{t('drugs.add')}</Button>}
        </div>
      </div>

      <Card className="overflow-x-auto p-0">
        <table className="w-full text-left text-sm">
          <caption className="sr-only">{t('drugs.title')}</caption>
          <thead className="bg-muted">
            <tr>
              {(['code', 'name', 'atc', 'route', 'step', 'status'] as const).map((c) => (
                <th key={c} scope="col" className="px-3 py-2 font-semibold">{t(`drugs.col.${c}`)}</th>
              ))}
              <th scope="col" className="px-3 py-2"><span className="sr-only">{t('common.actions')}</span></th>
            </tr>
          </thead>
          <tbody>
            {q.isLoading && [0, 1, 2].map((i) => (
              <tr key={i}><td colSpan={7} className="px-3 py-2"><Skeleton className="h-6" /></td></tr>
            ))}
            {items.map((d) => (
              <tr key={d.id} className="border-t border-border">
                <td className="px-3 py-2 font-mono text-xs">{d.drug_code}</td>
                <td className="px-3 py-2">
                  <Link to={`/admin/drugs/${d.id}/rules`} className="text-primary underline">{d.drug_name}</Link>
                </td>
                <td className="px-3 py-2">{d.atc_code ?? '—'}</td>
                <td className="px-3 py-2">{d.route}</td>
                <td className="px-3 py-2">{d.rounding_step_mg}</td>
                <td className="px-3 py-2">
                  <Badge tone={d.is_active ? 'success' : 'neutral'}>
                    {d.is_active ? t('drugs.active') : t('drugs.archive')}
                  </Badge>
                </td>
                <td className="space-x-2 px-3 py-2 text-right">
                  <Button asChild size="sm" variant="outline">
                    <Link to={`/admin/drugs/${d.id}/rules`}>{t('drugs.rules')}</Link>
                  </Button>
                  {canEdit && d.is_active && (
                    <>
                      <Button size="sm" variant="outline" onClick={() => edit(d)}>{t('common.edit')}</Button>
                      <Button size="sm" variant="ghost"
                        onClick={() => { if (window.confirm(t('drugs.confirm', { name: d.drug_name }))) archive.mutate(d); }}>
                        {t('drugs.archive.action')}
                      </Button>
                    </>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {q.data && items.length === 0 && <p className="p-6 text-center text-muted-foreground">{t('drugs.empty')}</p>}
        {q.isError && <p role="alert" className="p-6 text-destructive">{t('drugs.error')}</p>}
      </Card>

      <DrugDialog open={open} onOpenChange={setOpen} drug={editing} />
    </div>
  );
}
