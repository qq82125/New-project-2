import { HTMLAttributes } from 'react';
import { cn } from './cn';

type Props = HTMLAttributes<HTMLDivElement> & {
  width?: number | string;
  height?: number | string;
};

export function Skeleton({ className, width, height, style, ...props }: Props) {
  return (
    <div
      className={cn('ui-skeleton', className)}
      style={{ ...style, width, height }}
      aria-hidden="true"
      {...props}
    />
  );
}

