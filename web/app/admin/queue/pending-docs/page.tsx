import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../../../components/ui/card';
import PendingDocsQueueClient from '../../../../components/admin/queue/PendingDocsQueueClient';
import { adminFetchJson } from '../../../../lib/admin';

type Item = {
  id: string;
  raw_document_id: string;
  source_run_id?: number | null;
  reason_code: string;
  status: string;
  created_at?: string | null;
};

type Resp = { code: number; message: string; data: { items: Item[]; count: number; total?: number } };

export const dynamic = 'force-dynamic';

export default async function AdminQueuePendingDocsPage() {
  const data = await adminFetchJson<Resp['data']>('/api/admin/pending-documents?status=pending&limit=20&offset=0&order_by=created_at%20desc').catch(
    () => ({ items: [] as Item[] })
  );
  return (
    <div className="grid">
      <Card>
        <CardHeader>
          <CardTitle>待处理文档</CardTitle>
          <CardDescription>队列页：支持筛选、分页加载与批量忽略。</CardDescription>
        </CardHeader>
        <CardContent />
      </Card>
      <PendingDocsQueueClient initialItems={data?.items || []} />
    </div>
  );
}
