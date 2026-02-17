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
  id: number | null;
  source_key: string;
  entity_scope?: string;
  name: string;
  type: string;
  is_active: boolean;
  enabled: boolean;
  updated_at: string;
  compat?: {
    bound?: boolean;
    mode?: string;
    legacy_name?: string;
    legacy_type?: string;
    legacy_exists?: boolean;
    legacy_data_source_id?: number | null;
    legacy_is_active?: boolean;
  } | null;
  config_preview: { host: string; port: number; database: string; username: string; sslmode?: string | null; source_table?: string | null; source_query?: string | null; folder?: string | null; ingest_new?: boolean; ingest_chunk_size?: number };
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
  source_key?: string;
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
  const res = await fetch(`${API_BASE}/api/admin/sources`, {
    method: 'GET',
    headers: cookie ? { cookie } : undefined,
    cache: 'no-store',
  });

  if (res.status === 401) redirect('/login');
  if (res.status === 403) notFound();
  if (!res.ok) throw new Error(`admin/sources failed: ${res.status}`);

  const body = (await res.json()) as ApiResp<{
    items: Array<{
      source_key: string;
      display_name: string;
      entity_scope?: string;
      enabled_by_default: boolean;
      config?: { enabled?: boolean; updated_at?: string | null; fetch_params?: Record<string, unknown> };
      compat?: DataSource['compat'];
    }>;
  }>;
  if (body.code !== 0) throw new Error(body.message || 'admin/sources returned error');
  return (body.data.items || []).map((item) => {
    const fp = (item.config?.fetch_params || {}) as Record<string, unknown>;
    const legacy = (fp.legacy_data_source || {}) as Record<string, unknown>;
    const legacyCfg = (legacy.config || fp.connection || {}) as Record<string, unknown>;
    const t = String(legacy.type || item.compat?.legacy_type || 'postgres');
    const type = t === 'local_registry' ? 'local_registry' : 'postgres';
    return {
      id: item.compat?.legacy_data_source_id ?? null,
      source_key: item.source_key,
      entity_scope: String(item?.entity_scope || ''),
      name: String(legacy.name || item.display_name || item.source_key),
      type,
      is_active: Boolean(item.compat?.legacy_is_active),
      enabled: Boolean(item.config?.enabled ?? item.enabled_by_default),
      updated_at: String(item.config?.updated_at || ''),
      compat: item.compat || null,
      config_preview: {
        host: String(legacyCfg.host || ''),
        port: Number(legacyCfg.port || 5432),
        database: String(legacyCfg.database || ''),
        username: String(legacyCfg.username || ''),
        sslmode: (legacyCfg.sslmode ? String(legacyCfg.sslmode) : null),
        source_table: (legacyCfg.source_table ? String(legacyCfg.source_table) : 'public.products'),
        source_query: (legacyCfg.source_query ? String(legacyCfg.source_query) : null),
        folder: (legacyCfg.folder ? String(legacyCfg.folder) : null),
        ingest_new: legacyCfg.ingest_new !== false,
        ingest_chunk_size: Number(legacyCfg.ingest_chunk_size || 2000),
      },
    };
  });
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
  const sourceKey = String(params.source_key || '').trim().toUpperCase();

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
          <span className="muted">·</span>
          <Link href="/admin/conflicts" className="muted">
            冲突队列
          </Link>
        </CardContent>
      </Card>

      <DataSourcesManager initialItems={items} initialSourceKey={sourceKey} />
      <SyncManager initialItems={runs} initialPage={page} initialPageSize={pageSize} />
    </div>
  );
}
