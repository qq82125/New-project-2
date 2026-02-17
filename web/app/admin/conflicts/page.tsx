import { headers } from 'next/headers';
import Link from 'next/link';
import { notFound, redirect } from 'next/navigation';

import ConflictsQueueManager from '../../../components/admin/ConflictsQueueManager';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../../components/ui/card';

import { apiBase } from '../../../lib/api-server';

type AdminMe = { id: number; email: string; role: string };
type AdminMeResp = { code: number; message: string; data: AdminMe };
type ConflictItem = {
  id: string;
  registration_no: string;
  registration_id?: string | null;
  field_name: string;
  candidates: Array<{ source_key?: string; value?: string; observed_at?: string }>;
  status: string;
  winner_value?: string | null;
  winner_source_key?: string | null;
  source_run_id?: number | null;
  resolved_by?: string | null;
  resolved_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};
type ConflictsResp = {
  code: number;
  message: string;
  data: { items: ConflictItem[]; count: number; status: string };
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

async function getConflicts(): Promise<ConflictItem[]> {
  const API_BASE = apiBase();
  const cookie = (await headers()).get('cookie') || '';

  const tryFetch = async (path: string) => {
    const res = await fetch(`${API_BASE}${path}`, {
      method: 'GET',
      headers: cookie ? { cookie } : undefined,
      cache: 'no-store',
    });
    return res;
  };

  let res = await tryFetch('/api/admin/conflicts?status=open&limit=200');
  if (res.status === 404) {
    res = await tryFetch('/api/admin/conflicts-queue?status=open&limit=200');
  }
  if (res.status === 401) redirect('/login');
  if (res.status === 403) notFound();
  if (!res.ok) throw new Error(`admin/conflicts failed: ${res.status}`);

  const body = (await res.json()) as ConflictsResp;
  if (body.code !== 0) throw new Error(body.message || 'admin/conflicts returned error');
  return body.data?.items || [];
}

export default async function AdminConflictsPage() {
  const [me, items] = await Promise.all([getAdminMe(), getConflicts()]);
  return (
    <div className="grid">
      <Card>
        <CardHeader>
          <CardTitle>冲突队列管理</CardTitle>
          <CardDescription>仅 admin 可访问。默认使用新接口 `/api/admin/conflicts`。</CardDescription>
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

      <ConflictsQueueManager initialItems={items} />
    </div>
  );
}
