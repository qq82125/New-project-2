import { EmptyState } from '../States';
import { Table, TableWrap } from '../ui/table';

export type VariantRow = {
  di: string;
  model_spec?: string | null;
  manufacturer?: string | null;
  packaging?: string | null;
};

export default function VariantsTable({ rows }: { rows: VariantRow[] }) {
  if (!rows.length) {
    return <EmptyState text="暂无 DI/规格数据" />;
  }

  return (
    <TableWrap>
      <Table>
        <thead>
          <tr>
            <th>DI</th>
            <th>规格/型号</th>
            <th>注册人/生产商</th>
            <th>包装层级</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, idx) => (
            <tr key={`${row.di}:${idx}`}>
              <td>{row.di || '-'}</td>
              <td>{row.model_spec || '-'}</td>
              <td>{row.manufacturer || '-'}</td>
              <td>{row.packaging || '-'}</td>
            </tr>
          ))}
        </tbody>
      </Table>
    </TableWrap>
  );
}
