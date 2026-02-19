import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../../../components/ui/card';
import PendingDocsQueueClient from '../../../../components/admin/queue/PendingDocsQueueClient';
import { adminFetchJson } from '../../../../lib/admin';
import { EmptyState, ErrorState } from '../../../../components/States';

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
  let data: Resp['data'] | null = null;
  let error: string | null = null;
  try {
    data = await adminFetchJson<Resp['data']>('/api/admin/pending-documents?status=pending&limit=20&offset=0&order_by=created_at%20desc');
  } catch (e) {
    error = e instanceof Error ? e.message : '加载失败，请重试';
  }

  return (
    <div className="grid">
      <Card>
        <CardHeader>
          <h1>待处理文档</h1>
          <CardTitle>待处理文档</CardTitle>
          <CardDescription>队列页：支持筛选、分页加载与批量忽略。</CardDescription>
        </CardHeader>
        <CardContent />
      </Card>
      {error ? <ErrorState text={`加载失败，请重试（${error}）`} /> : null}
      {!error && (!data || (data.items || []).length === 0) ? <EmptyState text="暂无数据" /> : null}
      {!error ? <PendingDocsQueueClient initialItems={data?.items || []} /> : null}
    </div>
  );
}
