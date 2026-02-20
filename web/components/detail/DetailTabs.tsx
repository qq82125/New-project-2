'use client';

import { useMemo, useState, type ReactNode } from 'react';
import { Button } from '../ui/button';

export type DetailTabKey = 'overview' | 'changes' | 'evidence' | 'variants';

type DetailTabItem = {
  key: DetailTabKey;
  label: string;
  content: ReactNode;
};

export default function DetailTabs({ items }: { items: DetailTabItem[] }) {
  const [activeKey, setActiveKey] = useState<DetailTabKey>(items[0]?.key || 'overview');
  const active = useMemo(() => items.find((item) => item.key === activeKey) || items[0], [items, activeKey]);

  return (
    <div className="grid">
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        {items.map((item) => (
          <Button
            key={item.key}
            type="button"
            size="sm"
            variant={item.key === active?.key ? 'default' : 'secondary'}
            onClick={() => setActiveKey(item.key)}
          >
            {item.label}
          </Button>
        ))}
      </div>
      <div>{active?.content}</div>
    </div>
  );
}
