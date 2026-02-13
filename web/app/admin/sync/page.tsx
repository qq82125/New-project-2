import { headers } from 'next/headers';
import { notFound, redirect } from 'next/navigation';

import SyncManager from '../../../components/admin/SyncManager';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../../components/ui/card';

const API_BASE = process.env.API_BASE_URL || process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

type SourceRun = {
  id: number;
  source: string;
  status: string;
  message?: string | null;
  records_total: number;
  records_success: number;
  records_failed: number;
  added_count: number;
  updated_count: number;
  removed_count: number;
  started_at: string;
  finished_at?: string | null;
};

type ApiResp<T> = { code: number; message: string; data: T };

async function getAdminMeOrThrow() {
  const cookie = (await headers()).get('cookie') || '';
  const res = await fetch(`${API_BASE}/api/admin/me`, {
    method: 'GET',
    headers: cookie ? { cookie } : undefined,
    cache: 'no-store',
  });
  if (res.status === 401) redirect('/login');
  if (res.status === 403) notFound();
  if (!res.ok) throw new Error(`admin/me failed: ${res.status}`);
}

async function getRuns(): Promise<SourceRun[]> {
  const cookie = (await headers()).get('cookie') || '';
  const res = await fetch(`${API_BASE}/api/admin/source-runs?limit=50`, {
    method: 'GET',
    headers: cookie ? { cookie } : undefined,
    cache: 'no-store',
  });
  if (res.status === 401) redirect('/login');
  if (res.status === 403) notFound();
  if (!res.ok) return [];
  const body = (await res.json()) as ApiResp<{ items: SourceRun[] }>;
  if (body.code !== 0) return [];
  return body.data.items || [];
}

export const dynamic = 'force-dynamic';

export default async function AdminSyncPage() {
  await getAdminMeOrThrow();
  const runs = await getRuns();

  return (
    <div className="grid">
      <Card>
        <CardHeader>
          <CardTitle>同步控制</CardTitle>
          <CardDescription>查看同步记录并手动触发同步任务。</CardDescription>
        </CardHeader>
        <CardContent className="muted">需要 admin 权限。</CardContent>
      </Card>

      <SyncManager initialItems={runs} />
    </div>
  );
}

