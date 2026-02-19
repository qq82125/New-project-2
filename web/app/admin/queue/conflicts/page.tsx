import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../../../components/ui/card';
import ConflictsQueueClient from '../../../../components/admin/queue/ConflictsQueueClient';
import { adminFetchJson } from '../../../../lib/admin';

type Item = {
  id: string;
  registration_no: string;
  field_name: string;
  status: string;
  created_at?: string | null;
};

type Resp = { code: number; message: string; data: { items: Item[]; count: number; status: string } };

export const dynamic = 'force-dynamic';

export default async function AdminQueueConflictsPage() {
  const data = await adminFetchJson<Resp['data']>('/api/admin/conflicts?status=open&limit=20').catch(() => ({ items: [] as Item[] }));
  return (
    <div className="grid">
      <Card>
        <CardHeader>
          <CardTitle data-testid="admin_queue__header__title">冲突待裁决</CardTitle>
          <CardDescription>队列页：支持筛选、分页加载与批量标记已处理。</CardDescription>
        </CardHeader>
        <CardContent />
      </Card>
      <ConflictsQueueClient initialItems={data?.items || []} />
    </div>
  );
}
