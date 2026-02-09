import { ButtonHTMLAttributes } from 'react';
import { cn } from './cn';

type Props = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: 'default' | 'secondary' | 'ghost' | 'destructive';
  size?: 'sm' | 'md' | 'lg';
};

export function Button({
  className,
  variant = 'default',
  size = 'md',
  type = 'button',
  ...props
}: Props) {
  return (
    <button
      type={type}
      className={cn('ui-btn', `ui-btn--${variant}`, `ui-btn--${size}`, className)}
      {...props}
    />
  );
}

