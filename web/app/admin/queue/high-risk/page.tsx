import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../../../components/ui/card';
import HighRiskQueueClient from '../../../../components/admin/queue/HighRiskQueueClient';
import { adminFetchJson } from '../../../../lib/admin';
import { EmptyState, ErrorState } from '../../../../components/States';

type Item = {
  registration_no: string;
  product_name?: string | null;
  risk_level: string;
  lri_norm: number;
  calculated_at: string;
};

type Resp = { total: number; items: Item[] };

export const dynamic = 'force-dynamic';

export default async function AdminQueueHighRiskPage() {
  let data: Resp | null = null;
  let error: string | null = null;
  try {
    data = await adminFetchJson<Resp>('/api/admin/lri?limit=20&offset=0');
  } catch (e) {
    error = e instanceof Error ? e.message : '加载失败，请重试';
  }

  return (
    <div className="grid">
      <Card>
        <CardHeader>
          <h1>LRI 高风险</h1>
          <CardTitle>LRI 高风险</CardTitle>
          <CardDescription>队列页：支持筛选、分页加载与批量忽略。</CardDescription>
        </CardHeader>
        <CardContent />
      </Card>
      {error ? <ErrorState text={`加载失败，请重试（${error}）`} /> : null}
      {!error && (!data || (data.items || []).length === 0) ? <EmptyState text="暂无数据" /> : null}
      {!error ? <HighRiskQueueClient initialItems={data?.items || []} /> : null}
    </div>
  );
}
