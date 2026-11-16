import { Link } from 'react-router-dom';
import { t } from '@/i18n';

export function NotFoundPage() {
  return (
    <main className="mx-auto max-w-md p-8 text-center">
      <h1 className="text-2xl font-semibold">{t('notfound.title')}</h1>
      <p className="mt-2 text-muted-foreground">{t('notfound.text')}</p>
      <Link to="/" className="mt-4 inline-block text-primary underline">
        {t('notfound.home')}
      </Link>
    </main>
  );
}
