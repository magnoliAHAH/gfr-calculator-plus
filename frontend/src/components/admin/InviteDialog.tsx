import { useMutation } from '@tanstack/react-query';
import { useForm } from 'react-hook-form';
import { api, unwrap, type Schemas } from '@/api/client';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent } from '@/components/ui/dialog';
import { Field, Input, Select } from '@/components/ui/primitives';
import { t, tDynamic } from '@/i18n';
import { notifyError } from '@/lib/notify';

export const ASSIGNABLE_ROLES = ['org_admin', 'pharmacist', 'physician', 'auditor'] as const;

interface InviteForm {
  email: string;
  full_name: string;
  role: Schemas['UserInvite']['role'];
}

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onInvited: (u: Schemas['UserInvited']) => void;
}

export function InviteDialog({ open, onOpenChange, onInvited }: Props) {
  const { register, handleSubmit, reset, formState: { errors } } =
    useForm<InviteForm>({ defaultValues: { email: '', full_name: '', role: 'physician' } });

  const invite = useMutation({
    mutationFn: (v: InviteForm) => unwrap(api.POST('/admin/users', { body: v })),
    onSuccess: (u) => { reset(); onOpenChange(false); onInvited(u); },
    onError: notifyError,
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent title={t('users.invite')} description={t('users.invite.hint')}>
        <form onSubmit={handleSubmit((v) => invite.mutate(v))} className="space-y-3" noValidate>
          <Field label={t('users.col.email')} error={errors.email?.message}>
            {(f) => (
              <Input id={f.id} type="email" aria-invalid={f.invalid} aria-describedby={f.describedBy}
                {...register('email', {
                  required: t('validation.required'),
                  pattern: { value: /^[^@\s]+@[^@\s]+\.[^@\s]+$/, message: t('validation.email') },
                })} />
            )}
          </Field>
          <Field label={t('users.col.name')} error={errors.full_name?.message}>
            {(f) => (
              <Input id={f.id} aria-invalid={f.invalid} aria-describedby={f.describedBy}
                {...register('full_name', { required: t('validation.required') })} />
            )}
          </Field>
          <Field label={t('users.col.role')}>
            {(f) => (
              <Select id={f.id} {...register('role')}>
                {ASSIGNABLE_ROLES.map((r) => <option key={r} value={r}>{tDynamic('role', r)}</option>)}
              </Select>
            )}
          </Field>
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="outline" onClick={() => onOpenChange(false)}>{t('common.cancel')}</Button>
            <Button type="submit" disabled={invite.isPending}>{t('users.invite.submit')}</Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
