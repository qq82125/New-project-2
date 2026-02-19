'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Table, TableWrap } from '../ui/table';
import CopyButton from '../common/CopyButton';
import UnifiedBadge from '../common/UnifiedBadge';
import AddToBenchmarkButton from '../common/AddToBenchmarkButton';
import {
  DEFAULT_UNIFIED_COLUMNS,
  type UnifiedColumnKey,
  type UnifiedTableRow,
  UNIFIED_COLUMN_LABELS,
} from './columns';

export default function UnifiedTable({
  rows,
  columns = DEFAULT_UNIFIED_COLUMNS,
  emptyText = '暂无数据',
}: {
  rows: UnifiedTableRow[];
  columns?: UnifiedColumnKey[];
  emptyText?: string;
}) {
  const router = useRouter();

  if (rows.length === 0) {
    return <div className="muted">{emptyText}</div>;
  }

  return (
    <TableWrap>
      <Table>
        <thead>
          <tr>
            {columns.map((col) => (
              <th key={col}>{UNIFIED_COLUMN_LABELS[col]}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr
              key={row.id}
              style={{ cursor: row.detail_href ? 'pointer' : 'default' }}
              onClick={() => {
                if (row.detail_href) router.push(row.detail_href);
              }}
            >
              {columns.map((col) => {
                if (col === 'product_name') return <td key={col}>{row.product_name || '-'}</td>;
                if (col === 'company_name') return <td key={col}>{row.company_name || '-'}</td>;
                if (col === 'registration_no') {
                  return (
                    <td key={col}>
                      <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                        <span>{row.registration_no || '-'}</span>
                        {row.registration_no && row.registration_no !== '-' ? (
                          <span onClick={(e) => e.stopPropagation()}>
                            <CopyButton
                              text={row.registration_no}
                              label="复制"
                              size="sm"
                              successDescription="注册证号已复制"
                              errorDescription="请手动复制注册证号"
                            />
                          </span>
                        ) : null}
                      </div>
                    </td>
                  );
                }
                if (col === 'status') return <td key={col}>{row.status || '-'}</td>;
                if (col === 'expiry_date') return <td key={col}>{row.expiry_date || '-'}</td>;
                if (col === 'udi_di') return <td key={col}>{row.udi_di || '-'}</td>;
                if (col === 'badges') {
                  return (
                    <td key={col}>
                      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
                        {(row.badges || []).map((token, idx) => (
                          <UnifiedBadge key={`${token.kind}:${token.value}:${idx}`} token={token} />
                        ))}
                        {(row.badges || []).length === 0 ? '-' : null}
                      </div>
                    </td>
                  );
                }
                if (col === 'actions') {
                  return (
                    <td key={col}>
                      <div onClick={(e) => e.stopPropagation()}>
                        {row.action?.type === 'benchmark' && row.action.registration_no ? (
                          <AddToBenchmarkButton
                            registrationNo={row.action.registration_no}
                            setId={row.action.set_id || 'my-benchmark'}
                          />
                        ) : row.action?.href ? (
                          <Link className={`ui-btn ui-btn--sm ui-btn--secondary ${row.action.disabled ? 'is-disabled' : ''}`} href={row.action.href}>
                            {row.action.label || '查看'}
                          </Link>
                        ) : row.action?.label ? (
                          <button type="button" className="ui-btn ui-btn--sm ui-btn--secondary" disabled>
                            {row.action.label}
                          </button>
                        ) : (
                          <span className="muted">-</span>
                        )}
                      </div>
                    </td>
                  );
                }
                return <td key={col}>-</td>;
              })}
            </tr>
          ))}
        </tbody>
      </Table>
    </TableWrap>
  );
}
