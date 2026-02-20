'use client';

import Link from 'next/link';
import { useMemo, useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card';
import { buildSearchUrl, type SearchChangeType } from '../../lib/search-filters';

type TrendPoint = {
  metric_date: string;
  new_products: number;
  updated_products: number;
  cancelled_products: number;
};

type TrendTab = {
  key: SearchChangeType;
  label: string;
};

const TABS: TrendTab[] = [
  { key: 'new', label: '新增' },
  { key: 'update', label: '更新' },
  { key: 'cancel', label: '注销' },
];

function valueOf(point: TrendPoint, tab: SearchChangeType): number {
  if (tab === 'new') return Number(point.new_products || 0);
  if (tab === 'update') return Number(point.updated_products || 0);
  return Number(point.cancelled_products || 0);
}

export default function TrendEntry({ items }: { items: TrendPoint[] }) {
  const [active, setActive] = useState<SearchChangeType>('new');
  const rows = useMemo(() => items.slice(-30), [items]);
  const maxValue = useMemo(() => rows.reduce((m, p) => Math.max(m, valueOf(p, active)), 0), [rows, active]);
  const href = buildSearchUrl({ change_type: active, date_range: '30d', sort: 'recency' });

  return (
    <Card>
      <CardHeader>
        <CardTitle>趋势入口（30天）</CardTitle>
        <CardDescription>模块降级为可点击入口：切换 Tab 后点击趋势区或“查看全部”进入 Search。</CardDescription>
      </CardHeader>
      <CardContent style={{ paddingTop: 8, paddingBottom: 10 }}>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 8 }}>
          {TABS.map((tab) => (
            <button
              key={tab.key}
              type="button"
              className={`ui-btn ui-btn--sm ${active === tab.key ? 'ui-btn--default' : 'ui-btn--secondary'}`}
              onClick={() => setActive(tab.key)}
            >
              {tab.label}
            </button>
          ))}
          <Link href={href} className="ui-btn ui-btn--sm ui-btn--ghost">
            查看全部
          </Link>
        </div>

        <Link href={href} style={{ color: 'inherit' }}>
          <div style={{ display: 'grid', gap: 4, maxHeight: 92, overflow: 'hidden' }}>
            {rows.slice(-14).map((point) => {
              const value = valueOf(point, active);
              const pct = Math.max(6, Math.round((value / Math.max(1, maxValue)) * 100));
              return (
                <div key={point.metric_date} style={{ display: 'grid', gridTemplateColumns: '46px 1fr 36px', gap: 6, alignItems: 'center' }}>
                  <span className="muted" style={{ fontSize: 11 }}>{point.metric_date.slice(5)}</span>
                  <div style={{ height: 5, borderRadius: 999, background: 'rgba(23,107,82,0.14)' }}>
                    <div
                      style={{
                        width: `${pct}%`,
                        height: 5,
                        borderRadius: 999,
                        background: 'linear-gradient(90deg, #4f987f, #176b52)',
                      }}
                    />
                  </div>
                  <span style={{ fontSize: 11 }}>{value}</span>
                </div>
              );
            })}
          </div>
        </Link>
      </CardContent>
    </Card>
  );
}

