import * as DialogPrimitive from '@radix-ui/react-dialog';
import type { ReactNode } from 'react';
import { t } from '@/i18n';
import { cn } from '@/lib/utils';

export const Dialog = DialogPrimitive.Root;

interface ContentProps {
  title: string;
  description?: string;
  children: ReactNode;
  className?: string;
}

/** Модальное окно: фокус-ловушка, Esc и aria-атрибуты обеспечивает Radix (WCAG AA). */
export function DialogContent({ title, description, children, className }: ContentProps) {
  return (
    <DialogPrimitive.Portal>
      <DialogPrimitive.Overlay className="fixed inset-0 z-40 bg-black/50" />
      <DialogPrimitive.Content
        className={cn(
          'fixed left-1/2 top-1/2 z-50 max-h-[90vh] w-[95vw] max-w-lg -translate-x-1/2 -translate-y-1/2 overflow-y-auto rounded-lg border border-border bg-card p-6 shadow-lg',
          className,
        )}
      >
        <DialogPrimitive.Title className="text-lg font-semibold">{title}</DialogPrimitive.Title>
        {description ? (
          <DialogPrimitive.Description className="mt-1 text-sm text-muted-foreground">
            {description}
          </DialogPrimitive.Description>
        ) : (
          <DialogPrimitive.Description className="sr-only">{title}</DialogPrimitive.Description>
        )}
        <div className="mt-4">{children}</div>
        <DialogPrimitive.Close
          className="absolute right-3 top-3 rounded-md p-1 hover:bg-muted"
          aria-label={t('common.close')}
        >
          <span aria-hidden="true">✕</span>
        </DialogPrimitive.Close>
      </DialogPrimitive.Content>
    </DialogPrimitive.Portal>
  );
}
