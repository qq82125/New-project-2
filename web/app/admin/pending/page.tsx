import { headers } from 'next/headers';
import Link from 'next/link';
import { notFound, redirect } from 'next/navigation';

import PendingRecordsManager from '../../../components/admin/PendingRecordsManager';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../../components/ui/card';

import { apiBase } from '../../../lib/api-server';

type AdminMe = { id: number; email: string; role: string };
type AdminMeResp = { code: number; message: string; data: AdminMe };
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

async function getAdminMe(): Promise<AdminMe> {
  const API_BASE = apiBase();
  const cookie = (await headers()).get('cookie') || '';
  const res = await fetch(`${API_BASE}/api/admin/me`, {
    method: 'GET',
    headers: cookie ? { cookie } : undefined,
    cache: 'no-store',
  });

  if (res.status === 401) redirect('/login');
  if (res.status === 403) notFound();
  if (!res.ok) throw new Error(`admin/me failed: ${res.status}`);

  const body = (await res.json()) as AdminMeResp;
  if (body.code !== 0) throw new Error(body.message || 'admin/me returned error');
  return body.data;
}

async function getPendingInitial(): Promise<{ items: PendingItem[]; total: number }> {
  const API_BASE = apiBase();
  const cookie = (await headers()).get('cookie') || '';
  const res = await fetch(`${API_BASE}/api/admin/pending?status=open&limit=50&offset=0&order_by=created_at%20desc`, {
    method: 'GET',
    headers: cookie ? { cookie } : undefined,
    cache: 'no-store',
  });

  if (res.status === 401) redirect('/login');
  if (res.status === 403) notFound();
  if (!res.ok) throw new Error(`admin/pending failed: ${res.status}`);

  const body = (await res.json()) as PendingResp;
  if (body.code !== 0) throw new Error(body.message || 'admin/pending returned error');
  return {
    items: body.data?.items || [],
    total: Number(body.data?.total ?? body.data?.count ?? 0),
  };
}

async function getPendingStatsInitial(): Promise<PendingStatsResp['data'] | null> {
  const API_BASE = apiBase();
  const cookie = (await headers()).get('cookie') || '';
  const res = await fetch(`${API_BASE}/api/admin/pending/stats`, {
    method: 'GET',
    headers: cookie ? { cookie } : undefined,
    cache: 'no-store',
  });
  if (!res.ok) return null;
  const body = (await res.json()) as PendingStatsResp;
  if (body.code !== 0) return null;
  return body.data || null;
}

export default async function AdminPendingPage() {
  const [me, initial, stats] = await Promise.all([getAdminMe(), getPendingInitial(), getPendingStatsInitial()]);
  return (
    <div className="grid">
      <Card>
        <CardHeader>
          <CardTitle>Pending 记录管理</CardTitle>
          <CardDescription>仅 admin 可访问。用于跟踪 registration anchor 未解析记录的 backlog。</CardDescription>
        </CardHeader>
        <CardContent style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
          <span className="muted">当前：</span>
          <span className="muted">{me.email}</span>
          <span className="muted">({me.role})</span>
          <span className="muted">·</span>
          <Link href="/admin" className="muted">
            返回管理后台
          </Link>
        </CardContent>
      </Card>

      <PendingRecordsManager initialItems={initial.items} initialTotal={initial.total} initialStats={stats} />
    </div>
  );
}

