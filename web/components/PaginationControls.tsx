import Link from 'next/link';

import { Button } from './ui/button';
import { Input } from './ui/input';
import { qs } from '../lib/api';

type QueryValue = string | number | undefined | null;

export default function PaginationControls({
  basePath,
  params,
  page,
  pageSize,
  total,
  buildHref,
}: {
  basePath: string;
  params: Record<string, QueryValue>;
  page: number;
  pageSize: number;
  total: number;
  buildHref?: (page: number, pageSize: number) => string;
}) {
  const safePage = Math.max(1, Number(page || 1));
  const safePageSize = Math.max(1, Number(pageSize || 20));
  const totalPages = Math.max(1, Math.ceil(Math.max(0, Number(total || 0)) / safePageSize));

  const hrefFor = (targetPage: number) =>
    buildHref
      ? buildHref(targetPage, safePageSize)
      : `${basePath}${qs({ ...params, page: targetPage, page_size: safePageSize })}`;

  return (
    <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
      {safePage > 1 ? <Link href={hrefFor(1)}>首页</Link> : <span className="muted">首页</span>}
      {safePage > 1 ? <Link href={hrefFor(safePage - 1)}>上一页</Link> : <span className="muted">上一页</span>}
      {safePage < totalPages ? <Link href={hrefFor(safePage + 1)}>下一页</Link> : <span className="muted">下一页</span>}
      {safePage < totalPages ? <Link href={hrefFor(totalPages)}>末页</Link> : <span className="muted">末页</span>}
      <form method="GET" style={{ display: 'flex', gap: 8, alignItems: 'center', marginLeft: 8 }}>
        {Object.entries(params).map(([k, v]) => (
          <input key={k} type="hidden" name={k} value={v == null ? '' : String(v)} />
        ))}
        <input type="hidden" name="page_size" value={String(safePageSize)} />
        <span className="muted">跳转到</span>
        <Input name="page" defaultValue={String(safePage)} inputMode="numeric" style={{ width: 90 }} min={1} max={totalPages} />
        <Button type="submit" variant="secondary">
          前往
        </Button>
      </form>
    </div>
  );
}
