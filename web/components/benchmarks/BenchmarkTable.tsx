'use client';

import { useMemo, useState } from 'react';
import { Button } from '../ui/button';
import UnifiedTable from '../table/UnifiedTable';
import { BENCHMARK_COLUMNS } from '../table/columns';
import type { UnifiedTableRow } from '../table/columns';

type SortKey = 'change_count_30d' | 'di_count' | 'params_coverage' | 'risk_level';
type SortOrder = 'asc' | 'desc';

function riskScore(v: string | null | undefined): number {
  const x = String(v || '').toLowerCase();
  if (x.includes('high')) return 3;
  if (x.includes('medium')) return 2;
  if (x.includes('low')) return 1;
  return 0;
}

export default function BenchmarkTable({ rows, loading }: { rows: UnifiedTableRow[]; loading: boolean }) {
  const [sortKey, setSortKey] = useState<SortKey>('change_count_30d');
  const [sortOrder, setSortOrder] = useState<SortOrder>('desc');

  const sortedRows = useMemo(() => {
    const copy = [...rows];
    copy.sort((a, b) => {
      let av: number;
      let bv: number;
      if (sortKey === 'risk_level') {
        av = riskScore(a.risk_level);
        bv = riskScore(b.risk_level);
      } else {
        av = Number(a[sortKey] || 0);
        bv = Number(b[sortKey] || 0);
      }
      if (av === bv) return String(a.registration_no || '').localeCompare(String(b.registration_no || ''));
      return sortOrder === 'desc' ? bv - av : av - bv;
    });
    return copy;
  }, [rows, sortKey, sortOrder]);

  if (loading) {
    return <div className="muted">加载中...</div>;
  }

  return (
    <div className="grid" style={{ gap: 8 }}>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <Button type="button" size="sm" variant={sortKey === 'change_count_30d' ? 'default' : 'secondary'} onClick={() => setSortKey('change_count_30d')}>
          按30天变更
        </Button>
        <Button type="button" size="sm" variant={sortKey === 'di_count' ? 'default' : 'secondary'} onClick={() => setSortKey('di_count')}>
          按DI数量
        </Button>
        <Button type="button" size="sm" variant={sortKey === 'params_coverage' ? 'default' : 'secondary'} onClick={() => setSortKey('params_coverage')}>
          按参数覆盖
        </Button>
        <Button type="button" size="sm" variant={sortKey === 'risk_level' ? 'default' : 'secondary'} onClick={() => setSortKey('risk_level')}>
          按风险等级
        </Button>
        <Button type="button" size="sm" variant="ghost" onClick={() => setSortOrder((v) => (v === 'desc' ? 'asc' : 'desc'))}>
          {sortOrder === 'desc' ? '降序' : '升序'}
        </Button>
      </div>
      <UnifiedTable rows={sortedRows} columns={BENCHMARK_COLUMNS} emptyText="当前集合暂无条目" />
    </div>
  );
}
