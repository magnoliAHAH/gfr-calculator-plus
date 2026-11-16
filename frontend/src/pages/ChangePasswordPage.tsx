import { useForm } from 'react-hook-form';
import { useNavigate } from 'react-router-dom';
import { api, unwrapEmpty } from '@/api/client';
import { useAuth } from '@/auth/AuthContext';
import { homeFor } from '@/auth/permissions';
import { Button } from '@/components/ui/button';
import { Card, Field, Input } from '@/components/ui/primitives';
import { t } from '@/i18n';
import { notifyError, notifySuccess } from '@/lib/notify';

interface Form {
  current_password: string;
  new_password: string;
  repeat: string;
}

const MIN_LEN = 10;
const MAX_BYTES = 72; // ограничение bcrypt на бэкенде

export function ChangePasswordPage() {
  const { user, refresh } = useAuth();
  const navigate = useNavigate();
  const {
    register, handleSubmit, getValues, formState: { errors, isSubmitting },
  } = useForm<Form>();

  const onSubmit = async (v: Form) => {
    try {
      await unwrapEmpty(api.POST('/auth/change-password', {
        body: { current_password: v.current_password, new_password: v.new_password },
      }));
      await refresh();
      notifySuccess(t('password.changed'));
      if (user) navigate(homeFor(user.role), { replace: true });
    } catch (err) {
      notifyError(err);
    }
  };

  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center p-4">
      <h1 className="mb-1 text-2xl font-semibold">{t('password.title')}</h1>
      {user?.must_change_password && (
        <p className="mb-4 rounded-md bg-warning p-2 text-sm text-warning-foreground" role="status">
          {t('password.forced')}
        </p>
      )}
      <Card>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
          <Field label={t('password.current')} error={errors.current_password?.message}>
            {(f) => (
              <Input id={f.id} type="password" autoComplete="current-password" aria-invalid={f.invalid}
                aria-describedby={f.describedBy}
                {...register('current_password', { required: t('validation.required') })} />
            )}
          </Field>
          <Field label={t('password.new')} hint={t('password.hint', { min: MIN_LEN })} error={errors.new_password?.message}>
            {(f) => (
              <Input id={f.id} type="password" autoComplete="new-password" aria-invalid={f.invalid}
                aria-describedby={f.describedBy}
                {...register('new_password', {
                  required: t('validation.required'),
                  minLength: { value: MIN_LEN, message: t('password.hint', { min: MIN_LEN }) },
                  validate: (val) =>
                    new TextEncoder().encode(val).length <= MAX_BYTES || t('password.toolong'),
                })} />
            )}
          </Field>
          <Field label={t('password.repeat')} error={errors.repeat?.message}>
            {(f) => (
              <Input id={f.id} type="password" autoComplete="new-password" aria-invalid={f.invalid}
                aria-describedby={f.describedBy}
                {...register('repeat', {
                  required: t('validation.required'),
                  validate: (val) => val === getValues('new_password') || t('password.mismatch'),
                })} />
            )}
          </Field>
          <Button type="submit" className="w-full" disabled={isSubmitting}>
            {t('password.submit')}
          </Button>
        </form>
      </Card>
    </main>
  );
}
