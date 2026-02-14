import { headers } from 'next/headers';
import Link from 'next/link';
import { notFound, redirect } from 'next/navigation';

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../../components/ui/card';
import DataSourcesManager from '../../../components/admin/DataSourcesManager';
import SyncManager from '../../../components/admin/SyncManager';

import { apiBase } from '../../../lib/api-server';

type AdminMe = { id: number; email: string; role: string };
type AdminMeResp = { code: number; message: string; data: AdminMe };

type DataSource = {
  id: number;
  name: string;
  type: string;
  is_active: boolean;
  updated_at: string;
  config_preview: { host: string; port: number; database: string; username: string; sslmode?: string | null };
};

type ApiResp<T> = { code: number; message: string; data: T };
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
  ivd_kept_count?: number;
  non_ivd_skipped_count?: number;
  source_notes?: { ivd_classifier_version?: number } | null;
  started_at: string;
  finished_at?: string | null;
};

export const dynamic = 'force-dynamic';

type PageParams = {
  page?: string;
  page_size?: string;
};

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

async function getDataSources(): Promise<DataSource[]> {
  const API_BASE = apiBase();
  const cookie = (await headers()).get('cookie') || '';
  const res = await fetch(`${API_BASE}/api/admin/data-sources`, {
    method: 'GET',
    headers: cookie ? { cookie } : undefined,
    cache: 'no-store',
  });

  if (res.status === 401) redirect('/login');
  if (res.status === 403) notFound();
  if (!res.ok) throw new Error(`admin/data-sources failed: ${res.status}`);

  const body = (await res.json()) as ApiResp<{ items: DataSource[] }>;
  if (body.code !== 0) throw new Error(body.message || 'admin/data-sources returned error');
  return body.data.items || [];
}

async function getSourceRuns(page: number, pageSize: number): Promise<SourceRun[]> {
  const API_BASE = apiBase();
  const cookie = (await headers()).get('cookie') || '';
  const res = await fetch(`${API_BASE}/api/admin/source-runs?page=${encodeURIComponent(String(page))}&page_size=${encodeURIComponent(String(pageSize))}`, {
    method: 'GET',
    headers: cookie ? { cookie } : undefined,
    cache: 'no-store',
  });

  if (res.status === 401) redirect('/login');
  if (res.status === 403) notFound();
  if (!res.ok) throw new Error(`admin/source-runs failed: ${res.status}`);

  const body = (await res.json()) as ApiResp<{ items: SourceRun[] }>;
  if (body.code !== 0) throw new Error(body.message || 'admin/source-runs returned error');
  return body.data.items || [];
}

export default async function AdminDataSourcesPage({ searchParams }: { searchParams: Promise<PageParams> }) {
  const params = await searchParams;
  const page = Math.max(1, Number(params.page || '1'));
  const pageSize = Math.max(1, Number(params.page_size || '10'));

  const [me, items, runs] = await Promise.all([getAdminMe(), getDataSources(), getSourceRuns(page, pageSize)]);

  return (
    <div className="grid">
      <Card>
        <CardHeader>
          <CardTitle>数据源管理</CardTitle>
          <CardDescription>仅 admin 可访问。用于新增/编辑/测试/激活数据源（同一时间只能有一个 Active）。</CardDescription>
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

      <DataSourcesManager initialItems={items} />
      <SyncManager initialItems={runs} initialPage={page} initialPageSize={pageSize} />
    </div>
  );
}
