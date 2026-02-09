'use client';

import { dismiss, useToast } from './use-toast';
import { cn } from './cn';

export function Toaster() {
  const { toasts } = useToast();

  return (
    <div className="ui-toaster" aria-live="polite" aria-relevant="additions removals">
      {toasts.map((t) => (
        <div
          key={t.id}
          className={cn('ui-toast', t.variant === 'destructive' ? 'ui-toast--destructive' : undefined)}
          role="status"
        >
          <div className="ui-toast__body">
            {t.title ? <div className="ui-toast__title">{t.title}</div> : null}
            {t.description ? <div className="ui-toast__desc">{t.description}</div> : null}
          </div>
          <button className="ui-toast__close" onClick={() => dismiss(t.id)} aria-label="关闭提示">
            ×
          </button>
        </div>
      ))}
    </div>
  );
}

