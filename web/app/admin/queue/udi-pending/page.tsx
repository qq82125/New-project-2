import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../../../components/ui/card';
import UdiPendingQueueClient from '../../../../components/admin/queue/UdiPendingQueueClient';
import { adminFetchJson } from '../../../../lib/admin';

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
  const data = await adminFetchJson<Resp['data']>('/api/admin/udi/pending-links?status=PENDING&limit=20').catch(() => ({ items: [] as Item[] }));
  return (
    <div className="grid">
      <Card>
        <CardHeader>
          <CardTitle data-testid="admin_queue__header__title">UDI 待映射</CardTitle>
          <CardDescription>队列页：支持筛选、分页加载与批量标记已处理。</CardDescription>
        </CardHeader>
        <CardContent />
      </Card>
      <UdiPendingQueueClient initialItems={data?.items || []} />
    </div>
  );
}
