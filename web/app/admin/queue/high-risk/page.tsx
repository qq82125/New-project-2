import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../../../components/ui/card';
import HighRiskQueueClient from '../../../../components/admin/queue/HighRiskQueueClient';
import { adminFetchJson } from '../../../../lib/admin';

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
  const data = await adminFetchJson<Resp>('/api/admin/lri?limit=20&offset=0').catch(() => ({ items: [] as Item[] }));
  return (
    <div className="grid">
      <Card>
        <CardHeader>
          <CardTitle>LRI 高风险</CardTitle>
          <CardDescription>队列页：支持筛选、分页加载与批量忽略。</CardDescription>
        </CardHeader>
        <CardContent />
      </Card>
      <HighRiskQueueClient initialItems={data?.items || []} />
    </div>
  );
}
