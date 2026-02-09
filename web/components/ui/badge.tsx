import { HTMLAttributes } from 'react';
import { cn } from './cn';

type Props = HTMLAttributes<HTMLSpanElement> & {
  variant?: 'default' | 'muted' | 'success' | 'warning' | 'danger';
};

export function Badge({ className, variant = 'default', ...props }: Props) {
  return <span className={cn('ui-badge', `ui-badge--${variant}`, className)} {...props} />;
}

