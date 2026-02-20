'use client';

import { EmptyState } from '../States';
import UnifiedTable from '../table/UnifiedTable';
import type { UnifiedTableRow } from '../table/columns';

export default function SimilarItems({ rows }: { rows: UnifiedTableRow[] }) {
  if (!rows.length) {
    return <EmptyState text="暂无同类推荐" />;
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
        'badges',
        'actions',
      ]}
      emptyText="暂无同类推荐"
    />
  );
}
