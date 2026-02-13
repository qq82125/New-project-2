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
  items: Array<{
    id: number;
    change_type: string;
    change_date?: string | null;
    changed_at?: string | null;
    product: {
      id: string;
      name: string;
      reg_no?: string | null;
      udi_di: string;
      status: string;
      company?: { id: string; name: string } | null;
    };
  }>;
};

export default async function StatusPage() {
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

  const [res, statsRes, changesRes] = await Promise.all([
    apiGet<StatusData>('/api/status'),
    apiGet<ChangeStatsData>('/api/changes/stats?days=30'),
    isPro ? apiGet<ChangesListData>('/api/changes?days=30&limit=50') : Promise.resolve({ data: null, error: null }),
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
          <CardDescription>Free 仅展示统计；Pro 可查看产品级变化列表与详情。</CardDescription>
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
                    {k}: {v}
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
            <CardTitle>变化列表（Pro）</CardTitle>
            <CardDescription>产品级变化记录（最近 30 天）。</CardDescription>
          </CardHeader>
          <CardContent className="grid">
            {changesRes.error ? (
              <ErrorState text={`变化列表加载失败：${changesRes.error}`} />
            ) : !changesRes.data || changesRes.data.items.length === 0 ? (
              <EmptyState text="暂无变化记录" />
            ) : (
              <div className="list">
                {changesRes.data.items.map((x) => (
                  <Card key={x.id}>
                    <CardHeader>
                      <CardTitle>
                        <Link href={`/products/${x.product.id}`}>{x.product.name}</Link>
                      </CardTitle>
                      <CardDescription>
                        <span className="muted">type:</span> {x.change_type}
                        {' · '}
                        <span className="muted">at:</span>{' '}
                        {x.change_date ? new Date(x.change_date).toLocaleString() : x.changed_at ? new Date(x.changed_at).toLocaleString() : '-'}
                      </CardDescription>
                    </CardHeader>
                    <CardContent style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
                      <Badge variant="muted">reg_no: {x.product.reg_no || '-'}</Badge>
                      <Badge variant="muted">udi_di: {x.product.udi_di}</Badge>
                      <Link className="muted" href={`/changes/${x.id}`}>
                        查看详情
                      </Link>
                    </CardContent>
                  </Card>
                ))}
              </div>
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
              <span className="muted">started:</span> {new Date(run.started_at).toLocaleString()}
              {' · '}
              <span className="muted">finished:</span> {run.finished_at ? new Date(run.finished_at).toLocaleString() : '-'}
            </CardDescription>
          </CardHeader>
          <CardContent className="grid">
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
              <Badge variant={run.status === 'success' ? 'success' : run.status === 'failed' ? 'danger' : 'muted'}>
                status: {run.status}
              </Badge>
              <Badge variant="muted">
                records: {run.records_success}/{run.records_total} (failed {run.records_failed})
              </Badge>
              <Badge variant="muted">
                added/updated/removed: {run.added_count}/{run.updated_count}/{run.removed_count}
              </Badge>
            </div>
            <div className="muted">message: {run.message || '-'}</div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
