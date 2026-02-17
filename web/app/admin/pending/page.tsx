import PendingRecordsManager from '../../../components/admin/PendingRecordsManager';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../../components/ui/card';

import { adminFetch, adminFetchJson } from '../../../lib/admin';
import { ADMIN_TEXT } from '../../../constants/admin-i18n';

type PendingItem = {
  id: string;
  source_key: string;
  reason_code: string;
  status: string;
  created_at?: string | null;
  candidate_registry_no?: string | null;
  candidate_company?: string | null;
  candidate_product_name?: string | null;
  raw_document_id: string;
};
type PendingResp = {
  code: number;
  message: string;
  data: { items: PendingItem[]; count: number; total?: number };
};
type PendingStatsResp = {
  code: number;
  message: string;
  data: {
    by_source_key: Array<{ source_key: string; open: number; resolved: number; ignored: number }>;
    by_reason_code: Array<{ reason_code: string; open: number }>;
    backlog: {
      open_total: number;
      resolved_last_24h: number;
      resolved_last_7d: number;
      windows: { resolved_24h_hours: number; resolved_7d_days: number };
    };
  };
};

export const dynamic = 'force-dynamic';

async function getPendingInitial(): Promise<{ items: PendingItem[]; total: number }> {
  const body = await adminFetchJson<PendingResp['data']>('/api/admin/pending?status=open&limit=50&offset=0&order_by=created_at%20desc');
  return {
    items: body?.items || [],
    total: Number(body?.total ?? body?.count ?? 0),
  };
}

async function getPendingStatsInitial(): Promise<PendingStatsResp['data'] | null> {
  const res = await adminFetch('/api/admin/pending/stats', { allowNotOk: true });
  if (!res.ok) return null;
  const body = (await res.json()) as PendingStatsResp;
  if (body.code !== 0) return null;
  return body.data || null;
}

export default async function AdminPendingPage() {
  const [initial, stats] = await Promise.all([getPendingInitial(), getPendingStatsInitial()]);
  return (
    <div className="grid">
      <Card>
        <CardHeader>
          <CardTitle>{ADMIN_TEXT.modules.pending.title}</CardTitle>
          <CardDescription>{ADMIN_TEXT.modules.pending.description}</CardDescription>
        </CardHeader>
        <CardContent>
          <span className="muted">支持按状态/来源/原因筛选，并可在队列中手动完成注册锚点修复。</span>
        </CardContent>
      </Card>

      <PendingRecordsManager initialItems={initial.items} initialTotal={initial.total} initialStats={stats} />
    </div>
  );
}
