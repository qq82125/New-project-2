import { headers } from 'next/headers';
import Link from 'next/link';
import { notFound, redirect } from 'next/navigation';

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../../components/ui/card';
import ContactInfoManager from '../../../components/admin/ContactInfoManager';

import { apiBase } from '../../../lib/api-server';

type AdminMe = { id: number; email: string; role: string };
type AdminMeResp = { code: number; message: string; data: AdminMe };

type AdminConfigItem = { config_key: string; config_value: any; updated_at: string };
type AdminConfigsResp = { code: number; message: string; data: { items: AdminConfigItem[] } };

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

async function getContactConfig(): Promise<AdminConfigItem | null> {
  const API_BASE = apiBase();
  const cookie = (await headers()).get('cookie') || '';
  const res = await fetch(`${API_BASE}/api/admin/configs`, {
    method: 'GET',
    headers: cookie ? { cookie } : undefined,
    cache: 'no-store',
  });

  if (res.status === 401) redirect('/login');
  if (res.status === 403) notFound();
  if (!res.ok) throw new Error(`admin/configs failed: ${res.status}`);

  const body = (await res.json()) as AdminConfigsResp;
  if (body.code !== 0) throw new Error(body.message || 'admin/configs returned error');
  const items = body.data?.items || [];
  return items.find((x) => x.config_key === 'public_contact_info') || null;
}

export default async function AdminContactPage() {
  const [me, cfg] = await Promise.all([getAdminMe(), getContactConfig()]);

  return (
    <div className="grid">
      <Card>
        <CardHeader>
          <CardTitle>联系信息</CardTitle>
          <CardDescription>仅 admin 可访问。用于配置 /contact 页展示的联系方式。</CardDescription>
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

      <ContactInfoManager initialConfig={cfg} />
    </div>
  );
}

