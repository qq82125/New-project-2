import { SelectHTMLAttributes } from 'react';
import { cn } from './cn';

type Props = SelectHTMLAttributes<HTMLSelectElement>;

export function Select({ className, ...props }: Props) {
  return <select className={cn('ui-select', className)} {...props} />;
}

