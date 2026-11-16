import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useRef, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api, ApiProblem, downloadFile, unwrap, uploadRulesCsv } from '@/api/client';
import { RuleVersionDialog } from '@/components/admin/RuleVersionDialog';
import { VersionCard } from '@/components/admin/VersionCard';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/primitives';
import { t } from '@/i18n';
import { notifyError, notifySuccess } from '@/lib/notify';

export function AdminRulesPage() {
  const drugId = Number(useParams().id);
  const qc = useQueryClient();
  const fileRef = useRef<HTMLInputElement>(null);
  const [dialog, setDialog] = useState<{ open: boolean; indication: string | null }>({ open: false, indication: null });

  const q = useQuery({
    queryKey: ['admin', 'rules', drugId],
    enabled: Number.isInteger(drugId),
    queryFn: () => unwrap(api.GET('/admin/drugs/{drug_id}/rules', { params: { path: { drug_id: drugId } } })),
  });

  const importCsv = useMutation({
    mutationFn: (file: File) => uploadRulesCsv(file),
    onSuccess: (r) => {
      notifySuccess(t('rules.imported', { n: r.imported.length }));
      void qc.invalidateQueries({ queryKey: ['admin', 'rules'] });
    },
    onError: (err) => {
      notifyError(err);
      // Ошибки по строкам CSV: показываем первые, чтобы сразу исправить файл
      if (err instanceof ApiProblem) {
        err.fieldErrors.slice(0, 5).forEach((e) => notifyError(new ApiProblem(400, '', `${e.field}: ${e.message}`, null)));
      }
    },
    onSettled: () => { if (fileRef.current) fileRef.current.value = ''; },
  });

  if (q.error instanceof ApiProblem && q.error.status === 404) {
    return (
      <p role="alert">
        {t('rules.notfound')} <Link to="/admin/drugs" className="text-primary underline">{t('rules.back')}</Link>
      </p>
    );
  }

  const versions = q.data?.versions ?? [];
  const indications = [...new Set(versions.map((g) => g.indication))];
  const exportCsv = () => void downloadFile(`/admin/rules/export?drug_id=${drugId}`, 'dosage_rules.csv').catch(notifyError);

  return (
    <div className="space-y-4">
      <Link to="/admin/drugs" className="text-sm text-primary underline">{t('rules.back')}</Link>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-2xl font-semibold">{t('rules.title')}</h1>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={exportCsv}>{t('rules.export')}</Button>
          <input ref={fileRef} type="file" accept=".csv,text/csv" className="sr-only" aria-label={t('rules.import')}
            onChange={(e) => { const f = e.target.files?.[0]; if (f) importCsv.mutate(f); }} />
          <Button variant="outline" disabled={importCsv.isPending} onClick={() => fileRef.current?.click()}>
            {t('rules.import')}
          </Button>
          <Button onClick={() => setDialog({ open: true, indication: null })}>{t('rules.new')}</Button>
        </div>
      </div>
      <p className="text-sm text-muted-foreground">{t('rules.immutable')}</p>

      {q.isLoading && <Skeleton className="h-40" />}
      {q.data && versions.length === 0 && <p className="text-muted-foreground">{t('rules.empty')}</p>}

      {indications.map((ind) => (
        <section key={ind} aria-label={ind} className="space-y-2">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold">{ind}</h2>
            <Button size="sm" variant="outline" onClick={() => setDialog({ open: true, indication: ind })}>
              {t('rules.newversion')}
            </Button>
          </div>
          {versions.filter((g) => g.indication === ind).map((g) => <VersionCard key={g.version} group={g} />)}
        </section>
      ))}

      <RuleVersionDialog open={dialog.open} indication={dialog.indication} drugId={drugId}
        onOpenChange={(o) => setDialog((s) => ({ ...s, open: o }))} />
    </div>
  );
}
