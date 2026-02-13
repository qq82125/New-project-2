import { headers } from 'next/headers';
import { redirect } from 'next/navigation';
import Link from 'next/link';
import { EmptyState, ErrorState } from '../../components/States';
import { apiGet, qs } from '../../lib/api';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';
import { formatUdiDiDisplay, labelField, labelRunSource, labelRunStatus } from '../../lib/labelMap';

const API_BASE = process.env.API_BASE_URL || process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

type StatusData = {
  latest_runs: Array<{
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
  }>;
};

type MeResp = { code: number; message: string; data: { entitlements?: { can_export?: boolean } | null } };

type ChangeStatsData = { days: number; total: number; by_type: Record<string, number> };

type ChangesListData = {
  days: number;
  total: number;
  page: number;
  page_size: number;
  items: Array<{
    id: number;
    change_type: string;
    change_date: string;
    product: {
      id: string;
      name: string;
      reg_no?: string | null;
      udi_di?: string | null;
      status: string;
      company?: { id: string; name: string } | null;
    };
  }>;
};

function fmtType(t: string) {
  const s = (t || '').toLowerCase();
  if (s === 'new') return '新增';
  if (s === 'update' || s === 'updated') return '变更';
  if (s === 'expire' || s === 'expired') return '过期';
  if (s === 'cancel' || s === 'cancelled') return '注销';
  return t || '-';
}

async function fetchWithCookie<T>(path: string, cookie: string) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'GET',
    headers: cookie ? { cookie } : undefined,
    cache: 'no-store',
  });
  if (!res.ok) return { data: null as T | null, error: `请求失败 (${res.status})` };
  const body = (await res.json()) as { code: number; message: string; data: T };
  if (body.code !== 0) return { data: null as T | null, error: body.message || '接口返回异常' };
  return { data: body.data, error: null as string | null };
}

export default async function StatusPage({ searchParams }: { searchParams?: Promise<{ page?: string; page_size?: string }> }) {
  const cookie = (await headers()).get('cookie') || '';
  const meRes = await fetch(`${API_BASE}/api/auth/me`, {
    method: 'GET',
    headers: cookie ? { cookie } : undefined,
    cache: 'no-store',
  });
  if (meRes.status === 401) redirect('/login');
  const meBody = (await meRes.json()) as MeResp;
  const isPro = Boolean(meBody?.data?.entitlements?.can_export);

  const res = await apiGet<StatusData>('/api/status');
  const sp = (await searchParams) || {};
  const page = Number(sp.page || '1');
  const pageSize = Number(sp.page_size || '20');
  const days = 30;

  const statsRes = await fetchWithCookie<ChangeStatsData>(`/api/changes/stats${qs({ days })}`, cookie);
  const changesRes = isPro
    ? await fetchWithCookie<ChangesListData>(`/api/changes${qs({ days, page, page_size: pageSize })}`, cookie)
    : { data: null, error: null };

  if (res.error) {
    return <ErrorState text={`状态页加载失败：${res.error}`} />;
  }
  if (!res.data || res.data.latest_runs.length === 0) {
    return <EmptyState text="暂无同步状态数据" />;
  }

  return (
    <div className="grid">
      <Card>
        <CardHeader>
          <CardTitle>变化统计（近 30 天）</CardTitle>
          <CardDescription>Free 仅展示统计；Pro 可查看产品变化列表与详情。</CardDescription>
        </CardHeader>
        <CardContent style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
          {statsRes.error ? (
            <span className="muted">加载失败：{statsRes.error}</span>
          ) : !statsRes.data ? (
            <span className="muted">暂无数据</span>
          ) : (
            <>
              <Badge variant="muted">总变化：{statsRes.data.total}</Badge>
              <Badge variant="muted">新增：{statsRes.data.by_type.new || 0}</Badge>
              <Badge variant="muted">过期：{statsRes.data.by_type.expire || 0}</Badge>
              <Badge variant="muted">变更：{statsRes.data.by_type.update || 0}</Badge>
              <Badge variant="muted">注销：{statsRes.data.by_type.cancel || 0}</Badge>
              <Badge variant={isPro ? 'success' : 'muted'}>{isPro ? 'Pro' : 'Free'}</Badge>
            </>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>变化列表（Pro）</CardTitle>
          <CardDescription>产品级变化记录（最近 30 天）。</CardDescription>
        </CardHeader>
        <CardContent className="grid">
          {!isPro ? (
            <div className="muted">当前为 Free，仅展示统计；升级后可查看变化列表与详情。</div>
          ) : changesRes.error ? (
            <ErrorState text={`变化列表加载失败：${changesRes.error}`} />
          ) : !changesRes.data || changesRes.data.items.length === 0 ? (
            <EmptyState text="暂无变化记录" />
          ) : (
            <>
              <div className="list">
                {changesRes.data.items.map((it) => (
                  <Card key={it.id}>
                    <CardHeader>
                      <CardTitle style={{ display: 'flex', gap: 10, alignItems: 'baseline', flexWrap: 'wrap' }}>
                        <span>{it.product.name}</span>
                        <span className="muted">
                          type: {fmtType(it.change_type)} · at: {new Date(it.change_date).toLocaleString()}
                        </span>
                      </CardTitle>
                      <CardDescription>
                        <span className="muted">企业：</span>
                        {it.product.company ? (
                          <Link href={`/companies/${it.product.company.id}`}>{it.product.company.name}</Link>
                        ) : (
                          '-'
                        )}
                      </CardDescription>
                    </CardHeader>
                    <CardContent style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
                      <Badge variant="muted">{labelField('reg_no')}：{it.product.reg_no || '-'}</Badge>
                      <Badge variant="muted">{labelField('udi_di')}：{formatUdiDiDisplay(it.product.udi_di)}</Badge>
                      <Link href={`/products/${it.product.id}`}>查看详情</Link>
                    </CardContent>
                  </Card>
                ))}
              </div>

              <div style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
                {page > 1 ? (
                  <Link href={`/status${qs({ page: page - 1, page_size: pageSize })}`}>上一页</Link>
                ) : (
                  <span className="muted">上一页</span>
                )}
                <span className="muted">
                  第 {page} 页 / 每页 {pageSize} 条 / 共 {changesRes.data.total} 条
                </span>
                {page * pageSize < changesRes.data.total ? (
                  <Link href={`/status${qs({ page: page + 1, page_size: pageSize })}`}>下一页</Link>
                ) : (
                  <span className="muted">下一页</span>
                )}
              </div>
            </>
          )}
        </CardContent>
      </Card>

      {res.data.latest_runs.map((run) => (
        <Card key={run.id}>
          <CardHeader>
            <CardTitle>
              任务 #{run.id} <span className="muted">{labelRunSource(run.source)}</span>
            </CardTitle>
            <CardDescription>
              <span className="muted">{labelField('started_at')}：</span> {new Date(run.started_at).toLocaleString()}
              {' · '}
              <span className="muted">{labelField('finished_at')}：</span>{' '}
              {run.finished_at ? new Date(run.finished_at).toLocaleString() : '-'}
            </CardDescription>
          </CardHeader>
          <CardContent className="grid">
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
              <Badge variant={run.status === 'success' ? 'success' : run.status === 'failed' ? 'danger' : 'muted'}>
                {labelField('status')}：{labelRunStatus(run.status)}
              </Badge>
              <Badge variant="muted">
                {labelField('records')}：{run.records_success}/{run.records_total}（失败 {run.records_failed}）
              </Badge>
              <Badge variant="muted">
                {labelField('added_updated_removed')}：{run.added_count}/{run.updated_count}/{run.removed_count}
              </Badge>
            </div>
            <div className="muted">
              {labelField('message')}：{run.message || '-'}
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
