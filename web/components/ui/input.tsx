import { InputHTMLAttributes } from 'react';
import { cn } from './cn';

type Props = InputHTMLAttributes<HTMLInputElement>;

export function Input({ className, ...props }: Props) {
  return <input className={cn('ui-input', className)} {...props} />;
}

