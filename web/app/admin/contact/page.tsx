import { headers } from 'next/headers';
import { notFound, redirect } from 'next/navigation';

import AdminContactEditor from '../../../components/admin/AdminContactEditor';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../../components/ui/card';

const API_BASE = process.env.API_BASE_URL || process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

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

async function getContactConfig(): Promise<Record<string, any>> {
  const cookie = (await headers()).get('cookie') || '';
  const res = await fetch(`${API_BASE}/api/admin/configs`, {
    method: 'GET',
    headers: cookie ? { cookie } : undefined,
    cache: 'no-store',
  });
  if (res.status === 401) redirect('/login');
  if (res.status === 403) notFound();
  if (!res.ok) return {};
  const body = (await res.json()) as ApiResp<{ items: Array<{ config_key: string; config_value: any }> }>;
  if (body.code !== 0) return {};
  const found = (body.data.items || []).find((x) => x.config_key === 'contact_info');
  return (found?.config_value as Record<string, any>) || {};
}

export const dynamic = 'force-dynamic';

export default async function AdminContactPage() {
  await getAdminMeOrThrow();
  const initial = await getContactConfig();

  return (
    <div className="grid">
      <Card>
        <CardHeader>
          <CardTitle>联系人与渠道配置</CardTitle>
          <CardDescription>用于更新前台 /contact 页面展示的联系方式与渠道信息。</CardDescription>
        </CardHeader>
        <CardContent className="muted">保存后前台会优先展示此配置；为空则展示默认占位。</CardContent>
      </Card>

      <AdminContactEditor initialValue={initial} />
    </div>
  );
}

