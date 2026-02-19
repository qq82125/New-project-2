'use client';

import UnifiedTable from '../table/UnifiedTable';
import type { UnifiedTableRow } from '../table/columns';

export default function BenchmarkTable({ rows, loading }: { rows: UnifiedTableRow[]; loading: boolean }) {
  if (loading) {
    return <div className="muted">加载中...</div>;
  }

  return (
    <UnifiedTable
      rows={rows}
      columns={[
        'product_name',
        'company_name',
        'registration_no',
        'status',
        'expiry_date',
        'udi_di',
        'badges',
        'actions',
      ]}
      emptyText="当前集合暂无条目"
    />
  );
}
