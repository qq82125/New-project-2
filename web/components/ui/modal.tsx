import { useEffect } from 'react';

import { cn } from './cn';

export function Modal({
  open,
  title,
  onClose,
  children,
  footer,
  className,
}: {
  open: boolean;
  title: string;
  onClose: () => void;
  children: React.ReactNode;
  footer?: React.ReactNode;
  className?: string;
}) {
  useEffect(() => {
    if (!open) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="ui-modal__overlay" role="dialog" aria-modal="true" onMouseDown={onClose}>
      <div className={cn('ui-modal', className)} onMouseDown={(e) => e.stopPropagation()}>
        <div className="ui-modal__header">
          <div className="ui-modal__title">{title}</div>
          <button type="button" className="ui-modal__close" onClick={onClose} aria-label="关闭">
            ×
          </button>
        </div>
        <div className="ui-modal__body">{children}</div>
        {footer ? <div className="ui-modal__footer">{footer}</div> : null}
      </div>
    </div>
  );
}
