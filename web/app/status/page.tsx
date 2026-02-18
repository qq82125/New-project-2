import { headers } from 'next/headers';
import { redirect } from 'next/navigation';
import { EmptyState, ErrorState } from '../../components/States';
import { apiGet } from '../../lib/api';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';

import { apiBase } from '../../lib/api-server';
import { getMe } from '../../lib/getMe';
import ProUpgradeHint from '../../components/plan/ProUpgradeHint';
import Link from 'next/link';
import { PRO_COPY, PRO_TRIAL_HREF } from '../../constants/pro';
import { CHANGE_TYPE_ZH, FIELD_ZH, RUN_STATUS_ZH, labelFrom } from '../../constants/display';
import PaginationControls from '../../components/PaginationControls';

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

type ChangeStatsData = {
  days: number;
  total: number;
  by_type: Record<string, number>;
};

type ChangesListData = {
  days: number;
  total: number;
  page: number;
  page_size: number;
  items: Array<{
    id: number;
    change_type: string;
    change_date?: string | null;
    changed_at?: string | null;
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

type PageParams = {
  page?: string;
  page_size?: string;
};

export default async function StatusPage({ searchParams }: { searchParams: Promise<PageParams> }) {
  const API_BASE = apiBase();
  const cookie = (await headers()).get('cookie') || '';
  const meRes = await fetch(`${API_BASE}/api/auth/me`, {
    method: 'GET',
    headers: cookie ? { cookie } : undefined,
    cache: 'no-store',
  });
  if (meRes.status === 401) redirect('/login');

  const me = await getMe();
  const isPro = Boolean(me?.plan?.is_pro || me?.plan?.is_admin);

  const params = await searchParams;
  const page = Math.max(1, Number(params.page || '1'));
  const pageSize = Math.max(1, Number(params.page_size || '20'));

  const [res, statsRes, changesRes] = await Promise.all([
    apiGet<StatusData>('/api/status'),
    apiGet<ChangeStatsData>('/api/changes/stats?days=30'),
    isPro
      ? apiGet<ChangesListData>(`/api/changes?days=30&page=${encodeURIComponent(String(page))}&page_size=${encodeURIComponent(String(pageSize))}`)
      : Promise.resolve({ data: null, error: null }),
  ]);

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
          <CardDescription>免费版仅展示统计；专业版可查看产品级变化列表与详情。</CardDescription>
        </CardHeader>
        <CardContent className="grid">
          {statsRes.error ? (
            <ErrorState text={`统计加载失败：${statsRes.error}`} />
          ) : !statsRes.data ? (
            <EmptyState text="暂无统计数据" />
          ) : (
            <>
              <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
                <Badge variant="muted">总变化：{statsRes.data.total}</Badge>
                {Object.entries(statsRes.data.by_type || {}).map(([k, v]) => (
                  <Badge key={k} variant="muted">
                    {labelFrom(CHANGE_TYPE_ZH, k)}: {v}
                  </Badge>
                ))}
              </div>
              {!isPro ? (
                <ProUpgradeHint
                  text={PRO_COPY.status_free_hint}
                  ctaHref={PRO_TRIAL_HREF}
                />
              ) : null}
            </>
          )}
        </CardContent>
      </Card>

      {isPro ? (
        <Card>
          <CardHeader>
            <CardTitle>变化列表（专业版）</CardTitle>
            <CardDescription>产品级变化记录（最近 30 天）。</CardDescription>
          </CardHeader>
          <CardContent className="grid">
            {changesRes.error ? (
              <ErrorState text={`变化列表加载失败：${changesRes.error}`} />
            ) : !changesRes.data || changesRes.data.items.length === 0 ? (
              <EmptyState text="暂无变化记录" />
            ) : (
              <>
                <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
                  <Badge variant="muted">共 {changesRes.data.total} 条</Badge>
                  <span className="muted">
                    第 {changesRes.data.page} / {Math.max(1, Math.ceil(changesRes.data.total / Math.max(1, changesRes.data.page_size)))} 页（每页{' '}
                    {changesRes.data.page_size} 条）
                  </span>
                  <Link className="muted" href="/changes/export">
                    历史变化导出
                  </Link>
                </div>

                <div className="list">
                  {changesRes.data.items.map((x) => (
                    <Card key={x.id}>
                      <CardHeader>
                        <CardTitle>
                          <Link href={`/products/${x.product.id}`}>{x.product.name}</Link>
                        </CardTitle>
                        <CardDescription>
                          <span className="muted">{labelFrom(FIELD_ZH, 'change_type')}:</span> {labelFrom(CHANGE_TYPE_ZH, x.change_type)}
                          {' · '}
                          <span className="muted">时间:</span>{' '}
                          {x.change_date ? new Date(x.change_date).toLocaleString() : x.changed_at ? new Date(x.changed_at).toLocaleString() : '-'}
                        </CardDescription>
                      </CardHeader>
                      <CardContent className="grid">
                        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
                          <Badge variant="muted">
                            {labelFrom(FIELD_ZH, 'reg_no')}: {x.product.reg_no || '-'}
                          </Badge>
                          <Badge variant="muted">
                            {labelFrom(FIELD_ZH, 'udi_di')}: {x.product.udi_di || '-'}
                          </Badge>
                          <Link className="muted" href={`/changes/${x.id}`}>
                            查看详情
                          </Link>
                        </div>
                        <div>
                          <span className="muted">企业：</span>
                          {x.product.company?.id ? (
                            <Link href={`/companies/${x.product.company.id}`}>{x.product.company.name}</Link>
                          ) : (
                            '-'
                          )}
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>

                <Card>
                  <CardContent style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
                    <PaginationControls
                      basePath="/status"
                      params={{}}
                      page={changesRes.data.page}
                      pageSize={changesRes.data.page_size}
                      total={changesRes.data.total}
                    />
                  </CardContent>
                </Card>
              </>
            )}
          </CardContent>
        </Card>
      ) : null}

      {res.data.latest_runs.map((run) => (
        <Card key={run.id}>
          <CardHeader>
            <CardTitle>
              #{run.id} <span className="muted">{run.source}</span>
            </CardTitle>
            <CardDescription>
              <span className="muted">开始时间：</span> {new Date(run.started_at).toLocaleString()}
              {' · '}
              <span className="muted">结束时间：</span> {run.finished_at ? new Date(run.finished_at).toLocaleString() : '-'}
            </CardDescription>
          </CardHeader>
          <CardContent className="grid">
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
              <Badge variant={run.status === 'success' ? 'success' : run.status === 'failed' ? 'danger' : 'muted'}>
                状态: {labelFrom(RUN_STATUS_ZH, (run.status || '').toLowerCase())}
              </Badge>
              <Badge variant="muted">
                处理: {run.records_success}/{run.records_total} (失败 {run.records_failed})
              </Badge>
              <Badge variant="muted">
                新增/变更/移除: {run.added_count}/{run.updated_count}/{run.removed_count}
              </Badge>
            </div>
            <div className="muted">运行信息：{run.message || '-'}</div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
