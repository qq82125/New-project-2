import { headers } from 'next/headers';
import Link from 'next/link';
import { notFound, redirect } from 'next/navigation';

import UdiPendingLinksManager from '../../../components/admin/UdiPendingLinksManager';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../../components/ui/card';

import { apiBase } from '../../../lib/api-server';

type AdminMe = { id: number; email: string; role: string };
type AdminMeResp = { code: number; message: string; data: AdminMe };
type PendingItem = {
  id: string;
  di: string;
  status: string;
  reason: string;
  reason_code?: string | null;
  candidate_company_name?: string | null;
  candidate_product_name?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};
type PendingResp = {
  code: number;
  message: string;
  data: { items: PendingItem[]; count: number; status: string };
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

async function getPendingItems(): Promise<PendingItem[]> {
  const API_BASE = apiBase();
  const cookie = (await headers()).get('cookie') || '';
  const res = await fetch(`${API_BASE}/api/admin/udi/pending-links?status=PENDING&limit=200`, {
    method: 'GET',
    headers: cookie ? { cookie } : undefined,
    cache: 'no-store',
  });

  if (res.status === 401) redirect('/login');
  if (res.status === 403) notFound();
  if (!res.ok) throw new Error(`admin/udi/pending-links failed: ${res.status}`);

  const body = (await res.json()) as PendingResp;
  if (body.code !== 0) throw new Error(body.message || 'admin/udi/pending-links returned error');
  return body.data?.items || [];
}

export default async function AdminUdiLinksPage() {
  const [me, items] = await Promise.all([getAdminMe(), getPendingItems()]);
  return (
    <div className="grid">
      <Card>
        <CardHeader>
          <CardTitle>UDI 待映射管理</CardTitle>
          <CardDescription>仅 admin 可访问。用于处理 pending_udi_links 并手动绑定注册证号。</CardDescription>
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

      <UdiPendingLinksManager initialItems={items} />
    </div>
  );
}

