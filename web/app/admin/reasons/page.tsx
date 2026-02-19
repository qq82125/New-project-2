import Link from 'next/link';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../../components/ui/card';
import { adminFetchJson } from '../../../lib/admin';

type PendingStats = {
  by_reason_code: Array<{ reason_code: string; pending: number }>;
};

export const dynamic = 'force-dynamic';

export default async function AdminReasonsPage() {
  const stats = await adminFetchJson<PendingStats>('/api/admin/pending-documents/stats').catch(() => ({ by_reason_code: [] }));
  const items = (stats?.by_reason_code || []).slice(0, 30);
  return (
    <div className="grid">
      <Card>
        <CardHeader>
          <CardTitle>抓取失败原因码</CardTitle>
          <CardDescription>原因码 TOP，点击进入详情与工单复制。</CardDescription>
        </CardHeader>
        <CardContent>
          {items.length === 0 ? (
            <div className="muted">暂无数据</div>
          ) : (
            <div className="grid" style={{ gap: 6 }}>
              {items.map((x) => (
                <div key={x.reason_code} className="admin-mini-row">
                  <span className="admin-mini-row__k">{x.reason_code || 'UNKNOWN'}</span>
                  <span className="admin-mini-row__v">{x.pending}</span>
                  <Link className="admin-mini-row__a" href={`/admin/reasons/${encodeURIComponent(x.reason_code || 'UNKNOWN')}`}>
                    查看
                  </Link>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
