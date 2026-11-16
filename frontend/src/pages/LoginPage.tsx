import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '@/auth/AuthContext';
import { homeFor } from '@/auth/permissions';
import { Button } from '@/components/ui/button';
import { Card, Field, Input } from '@/components/ui/primitives';
import { ApiProblem } from '@/api/client';
import { t } from '@/i18n';

interface Form {
  email: string;
  password: string;
}

export function LoginPage() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register, handleSubmit, formState: { errors, isSubmitting },
  } = useForm<Form>();

  if (user) return <Navigate to={user.must_change_password ? '/change-password' : homeFor(user.role)} replace />;

  const from = (location.state as { from?: string } | null)?.from;

  const onSubmit = async (values: Form) => {
    setFormError(null);
    try {
      const u = await login(values.email, values.password);
      navigate(u.must_change_password ? '/change-password' : from ?? homeFor(u.role), { replace: true });
    } catch (err) {
      // 401 — неверные данные; остальное (сеть, 5xx) показываем отдельным текстом
      setFormError(err instanceof ApiProblem && err.status === 401 ? t('login.invalid') : t('error.unexpected'));
    }
  };

  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center p-4">
      <h1 className="mb-1 text-2xl font-semibold">{t('app.title')}</h1>
      <p className="mb-4 text-sm text-muted-foreground">{t('login.subtitle')}</p>
      <Card>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
          <Field label={t('login.email')} error={errors.email?.message}>
            {(f) => (
              <Input
                id={f.id} type="email" autoComplete="username" aria-invalid={f.invalid}
                aria-describedby={f.describedBy}
                {...register('email', { required: t('validation.required') })}
              />
            )}
          </Field>
          <Field label={t('login.password')} error={errors.password?.message}>
            {(f) => (
              <Input
                id={f.id} type="password" autoComplete="current-password" aria-invalid={f.invalid}
                aria-describedby={f.describedBy}
                {...register('password', { required: t('validation.required') })}
              />
            )}
          </Field>
          {formError && (
            <p role="alert" className="rounded-md bg-destructive/10 p-2 text-sm text-destructive">
              {formError}
            </p>
          )}
          <Button type="submit" className="w-full" disabled={isSubmitting}>
            {isSubmitting ? t('common.loading') : t('login.submit')}
          </Button>
        </form>
      </Card>
      <p className="mt-4 text-center text-sm">
        <Link to="/demo" className="text-primary underline">
          {t('login.demo')}
        </Link>
      </p>
    </main>
  );
}
