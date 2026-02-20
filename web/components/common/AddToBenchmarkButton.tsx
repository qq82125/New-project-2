'use client';

import { useMemo } from 'react';
import { Button } from '../ui/button';
import { isInBenchmarkSet, useBenchmarkSets } from '../../lib/benchmarks-store';

export default function AddToBenchmarkButton({
  registrationNo,
  setId = 'my-benchmark',
  size = 'sm',
  variant = 'secondary',
}: {
  registrationNo: string;
  setId?: string;
  size?: 'sm' | 'md' | 'lg';
  variant?: 'default' | 'secondary' | 'ghost' | 'destructive';
}) {
  const no = String(registrationNo || '').trim();
  const { ready, sets, toggle } = useBenchmarkSets();

  const included = useMemo(() => isInBenchmarkSet(sets, setId, no), [sets, setId, no]);

  return (
    <Button
      type="button"
      size={size}
      variant={variant}
      disabled={!no || !ready}
      onClick={() => {
        if (!no) return;
        toggle(setId, no);
      }}
    >
      {!ready ? '加载中...' : included ? 'Remove' : 'Add'}
    </Button>
  );
}
