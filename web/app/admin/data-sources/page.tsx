import { headers } from 'next/headers';
import { notFound, redirect } from 'next/navigation';

import DataSourcesManager from '../../../components/admin/DataSourcesManager';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../../components/ui/card';

const API_BASE = process.env.API_BASE_URL || process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

type DataSource = {
  id: number;
  name: string;
  type: string;
  is_active: boolean;
  updated_at: string;
  config_preview: {
    host: string;
    port: number;
    database: string;
    username: string;
    sslmode?: string | null;
  };
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

async function getDataSources(): Promise<DataSource[]> {
  const cookie = (await headers()).get('cookie') || '';
  const res = await fetch(`${API_BASE}/api/admin/data-sources`, {
    method: 'GET',
    headers: cookie ? { cookie } : undefined,
    cache: 'no-store',
  });
  if (res.status === 401) redirect('/login');
  if (res.status === 403) notFound();
  if (!res.ok) return [];
  const body = (await res.json()) as ApiResp<{ items: DataSource[] }>;
  if (body.code !== 0) return [];
  return body.data.items || [];
}

export const dynamic = 'force-dynamic';

export default async function AdminDataSourcesPage() {
  await getAdminMeOrThrow();
  const items = await getDataSources();

  return (
    <div className="grid">
      <Card>
        <CardHeader>
          <CardTitle>数据源管理</CardTitle>
          <CardDescription>管理外部数据库连接与启用的数据源配置。</CardDescription>
        </CardHeader>
        <CardContent className="muted">密码仅加密存储，不会在界面回显。</CardContent>
      </Card>

      <DataSourcesManager initialItems={items} />
    </div>
  );
}

