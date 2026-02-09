import { HTMLAttributes, TableHTMLAttributes } from 'react';
import { cn } from './cn';

export function Table({ className, ...props }: TableHTMLAttributes<HTMLTableElement>) {
  return <table className={cn('ui-table', className)} {...props} />;
}

export function TableWrap({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('ui-table-wrap', className)} {...props} />;
}

