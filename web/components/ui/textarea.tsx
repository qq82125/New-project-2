import { TextareaHTMLAttributes } from 'react';
import { cn } from './cn';

type Props = TextareaHTMLAttributes<HTMLTextAreaElement>;

export function Textarea({ className, ...props }: Props) {
  return <textarea className={cn('ui-textarea', className)} {...props} />;
}

