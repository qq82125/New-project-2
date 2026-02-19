import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../../../components/ui/card';
import UdiPendingQueueClient from '../../../../components/admin/queue/UdiPendingQueueClient';
import { adminFetchJson } from '../../../../lib/admin';
import { EmptyState, ErrorState } from '../../../../components/States';

type Item = {
  id: string;
  di: string;
  status: string;
  reason: string;
  reason_code?: string | null;
  candidate_company_name?: string | null;
  candidate_product_name?: string | null;
  created_at?: string | null;
};

type Resp = { code: number; message: string; data: { items: Item[]; count: number; status: string } };

export const dynamic = 'force-dynamic';

export default async function AdminQueueUdiPendingPage() {
  let data: Resp['data'] | null = null;
  let error: string | null = null;
  try {
    data = await adminFetchJson<Resp['data']>('/api/admin/udi/pending-links?status=PENDING&limit=20');
  } catch (e) {
    error = e instanceof Error ? e.message : '加载失败，请重试';
  }

  return (
    <div className="grid">
      <Card>
        <CardHeader>
          <h1>UDI 待映射</h1>
          <CardTitle>UDI 待映射</CardTitle>
          <CardDescription>队列页：支持筛选、分页加载与批量标记已处理。</CardDescription>
        </CardHeader>
        <CardContent />
      </Card>
      {error ? <ErrorState text={`加载失败，请重试（${error}）`} /> : null}
      {!error && (!data || (data.items || []).length === 0) ? <EmptyState text="暂无数据" /> : null}
      {!error ? <UdiPendingQueueClient initialItems={data?.items || []} /> : null}
    </div>
  );
}
