'use client';

import { Button } from '../ui/button';
import type { BenchmarkSet } from '../../lib/benchmarks-store';

export default function BenchmarkSets({
  sets,
  activeSetId,
  onSelect,
}: {
  sets: BenchmarkSet[];
  activeSetId: string;
  onSelect: (id: string) => void;
}) {
  return (
    <div className="grid">
      {sets.map((set) => (
        <Button
          key={set.id}
          type="button"
          size="sm"
          variant={set.id === activeSetId ? 'default' : 'secondary'}
          onClick={() => onSelect(set.id)}
          style={{ justifyContent: 'space-between', width: '100%' }}
        >
          <span>{set.name}</span>
          <span>{set.items.length}</span>
        </Button>
      ))}
    </div>
  );
}
