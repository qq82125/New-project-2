import { headers } from 'next/headers';
import { redirect } from 'next/navigation';
import Link from 'next/link';
import { EmptyState, ErrorState } from '../components/States';
import { apiGet, qs } from '../lib/api';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Table, TableWrap } from '../components/ui/table';
import { Badge } from '../components/ui/badge';

import { apiBase } from '../lib/api-server';
import PlanDebugServer from '../components/plan/PlanDebugServer';
import PlanBanner from '../components/plan/PlanBanner';
import RestrictedHint from '../components/plan/RestrictedHint';
import { PRO_COPY } from '../constants/pro';

type StatusData = {
  latest_runs: Array<{
    id: number;
    status: string;
    started_at: string;
    records_total: number;
    records_success: number;
    records_failed: number;
  }>;
};

type SummaryData = {
  start_date: string;
  end_date: string;
  total_new: number;
  total_updated: number;
  total_removed: number;
  latest_active_subscriptions: number;
};

type TrendData = {
  items: Array<{
    metric_date: string;
    new_products: number;
    updated_products: number;
    cancelled_products: number;
  }>;
};

type RankingsData = {
  top_new_days: Array<{ metric_date: string; value: number }>;
  top_removed_days: Array<{ metric_date: string; value: number }>;
};

type RadarData = {
  metric_date: string | null;
  items: Array<{ metric: string; value: number }>;
};

type SearchData = {
  items: Array<{
    product: {
      id: string;
      name: string;
      reg_no?: string | null;
      company?: { id: string; name: string } | null;
      expiry_date?: string | null;
    };
  }>;
};

function toCompanyRanking(items: SearchData['items']): Array<{ name: string; count: number }> {
  const map = new Map<string, number>();
  items.forEach((x) => {
    const name = x.product.company?.name;
    if (!name) return;
    map.set(name, (map.get(name) || 0) + 1);
  });
  return Array.from(map.entries())
    .map(([name, count]) => ({ name, count }))
    .sort((a, b) => b.count - a.count)
    .slice(0, 10);
}

function KpiCard({ label, value }: { label: string; value: number }) {
  return (
    <Card>
      <CardContent>
        <div className="muted" style={{ fontSize: 13 }}>{label}</div>
        <div style={{ fontSize: 30, fontWeight: 800, letterSpacing: 0.2 }}>{value}</div>
      </CardContent>
    </Card>
  );
}

const RADAR_METRIC_LABELS: Record<string, string> = {
  new_products: '新增产品数',
  updated_products: '更新产品数',
  cancelled_products: '注销产品数',
  expiring_in_90d: '90天内到期数',
  active_subscriptions: '活跃订阅数',
};

function formatRadarMetric(metric: string): string {
  return RADAR_METRIC_LABELS[metric] || metric;
}

function ProLockedState({ text }: { text: string }) {
  return (
    <div className="grid" style={{ gap: 10 }}>
      <div className="muted">{text}</div>
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
        <Badge variant="muted">Pro</Badge>
        <Link className="ui-btn" href="/contact?intent=pro">
          联系开通
        </Link>
      </div>
    </div>
  );
}

export default async function DashboardPage() {
  const API_BASE = apiBase();
  const cookie = (await headers()).get('cookie') || '';
  const meRes = await fetch(`${API_BASE}/api/auth/me`, {
    method: 'GET',
    headers: cookie ? { cookie } : undefined,
    cache: 'no-store',
  });
  if (meRes.status === 401) redirect('/login');

  let isPro = false;
  try {
    const body = (await meRes.json()) as any;
    const ent = body?.data?.entitlements || null;
    isPro = Boolean(ent?.can_export) || Number(ent?.trend_range_days || 0) > 30;
  } catch {
    isPro = false;
  }

  const [statusRes, summaryRes, trendRes, rankingsRes, radarRes, newProductRes, expiringRes] = await Promise.all([
    apiGet<StatusData>('/api/status'),
    apiGet<SummaryData>('/api/dashboard/summary?days=30'),
    apiGet<TrendData>('/api/dashboard/trend?days=30'),
    isPro ? apiGet<RankingsData>('/api/dashboard/rankings?days=30&limit=10') : Promise.resolve({ data: null, error: null }),
    isPro ? apiGet<RadarData>('/api/dashboard/radar') : Promise.resolve({ data: null, error: null }),
    apiGet<SearchData>(`/api/search${qs({ page: 1, page_size: 20, sort_by: 'approved_date', sort_order: 'desc' })}`),
    isPro
      ? apiGet<SearchData>(`/api/search${qs({ page: 1, page_size: 20, sort_by: 'expiry_date', sort_order: 'asc' })}`)
      : Promise.resolve({ data: null, error: null }),
  ]);
  const trendWindow = trendRes.data?.items.slice(-10) ?? [];
  const maxTrendValue = trendWindow.reduce((max, item) => Math.max(max, item.new_products), 0);

  return (
    <div className="grid">
      <Card>
        <CardHeader>
          <CardTitle>仪表盘</CardTitle>
          <CardDescription>聚合近 30 天关键指标、趋势与榜单。</CardDescription>
        </CardHeader>
        <CardContent className="grid" style={{ gap: 10 }}>
          <PlanBanner isPro={isPro} />
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
            <PlanDebugServer />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>同步状态</CardTitle>
          <CardDescription>最近一次同步任务与执行结果。</CardDescription>
        </CardHeader>
        <CardContent>
        {statusRes.error ? (
          <ErrorState text={`状态加载失败：${statusRes.error}`} />
        ) : !statusRes.data || statusRes.data.latest_runs.length === 0 ? (
          <EmptyState text="暂无同步记录" />
        ) : (
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
            <Badge variant={statusRes.data.latest_runs[0].status === 'success' ? 'success' : 'muted'}>
              {statusRes.data.latest_runs[0].status}
            </Badge>
            <div>
              最近一次：#{statusRes.data.latest_runs[0].id}，开始于{' '}
              {new Date(statusRes.data.latest_runs[0].started_at).toLocaleString()}
            </div>
          </div>
        )}
        </CardContent>
      </Card>

      <section className="kpis">
        {summaryRes.error || !summaryRes.data ? (
          <ErrorState text={`KPI 加载失败：${summaryRes.error || '未知错误'}`} />
        ) : (
          <>
            <KpiCard label="30 天新增" value={summaryRes.data.total_new} />
            <KpiCard label="30 天更新" value={summaryRes.data.total_updated} />
            <KpiCard label="30 天移除" value={summaryRes.data.total_removed} />
            <KpiCard label="活跃订阅" value={summaryRes.data.latest_active_subscriptions} />
          </>
        )}
      </section>

      <Card>
        <CardHeader>
          <CardTitle>新增趋势（30 天）</CardTitle>
          <CardDescription>最近 10 天新增产品变化（简易条形图）。</CardDescription>
        </CardHeader>
        <CardContent className="dashboard-compact">
        {trendRes.error ? (
          <ErrorState text={`趋势加载失败：${trendRes.error}`} />
        ) : !trendRes.data || trendRes.data.items.length === 0 ? (
          <EmptyState text="暂无趋势数据" />
        ) : (
          <div className="spark dashboard-spark">
            {trendWindow.map((item) => (
              <div key={item.metric_date} className="spark-row">
                <span>{item.metric_date.slice(5)}</span>
                <div
                  className="spark-bar"
                  style={{ width: `${Math.max(8, Math.round((item.new_products / Math.max(1, maxTrendValue)) * 100))}%` }}
                />
                <span>{item.new_products}</span>
              </div>
            ))}
          </div>
        )}
        </CardContent>
      </Card>

      <section className="columns-3">
        <Card>
          <CardHeader>
            <CardTitle>新增产品榜单</CardTitle>
            <CardDescription>按批准日期排序（取前 {isPro ? 10 : 5}）。</CardDescription>
          </CardHeader>
          <CardContent className="grid">
            {newProductRes.error ? (
              <ErrorState text={`加载失败：${newProductRes.error}`} />
            ) : !newProductRes.data || newProductRes.data.items.length === 0 ? (
              <EmptyState text="暂无新增产品" />
            ) : (
              <TableWrap>
                <Table>
                  <thead>
                    <tr>
                      <th>产品</th>
                    </tr>
                  </thead>
                  <tbody>
                    {newProductRes.data.items.slice(0, isPro ? 10 : 5).map((item) => (
                      <tr key={item.product.id}>
                        <td>
                          <Link href={`/products/${item.product.id}`}>{item.product.name}</Link>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </Table>
              </TableWrap>
            )}
            {!isPro ? <RestrictedHint /> : null}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>企业榜单</CardTitle>
            <CardDescription>基于新增产品前 20 条聚合（取前 {isPro ? 10 : 3}）。</CardDescription>
          </CardHeader>
          <CardContent className="grid">
            {newProductRes.error || !newProductRes.data ? (
              <ErrorState text={`加载失败：${newProductRes.error || '未知错误'}`} />
            ) : toCompanyRanking(newProductRes.data.items).length === 0 ? (
              <EmptyState text="暂无企业数据" />
            ) : (
              <TableWrap>
                <Table>
                  <thead>
                    <tr>
                      <th>企业</th>
                      <th style={{ width: 90 }}>数量</th>
                    </tr>
                  </thead>
                  <tbody>
                    {toCompanyRanking(newProductRes.data.items)
                      .slice(0, isPro ? 10 : 3)
                      .map((item) => (
                        <tr key={item.name}>
                          <td>
                            <Link href={`/search${qs({ company: item.name })}`}>{item.name}</Link>
                          </td>
                          <td>{item.count}</td>
                        </tr>
                      ))}
                  </tbody>
                </Table>
              </TableWrap>
            )}
            {!isPro ? <RestrictedHint /> : null}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>即将到期榜单</CardTitle>
            <CardDescription>按到期日升序（取前 10）。</CardDescription>
          </CardHeader>
          <CardContent className="grid">
            {!isPro ? (
              <div className="grid" style={{ gap: 10 }}>
                <div className="muted">即将到期数量：-</div>
                <div className="muted" style={{ fontSize: 13 }}>
                  {PRO_COPY.restricted_hint}
                </div>
              </div>
            ) : expiringRes.error ? (
              <ErrorState text={`加载失败：${expiringRes.error}`} />
            ) : !expiringRes.data || expiringRes.data.items.length === 0 ? (
              <EmptyState text="暂无到期数据" />
            ) : (
              <TableWrap>
                <Table>
                  <thead>
                    <tr>
                      <th>产品</th>
                      <th style={{ width: 120 }}>到期日</th>
                    </tr>
                  </thead>
                  <tbody>
                    {expiringRes.data.items.slice(0, 10).map((item) => (
                      <tr key={item.product.id}>
                        <td>
                          <Link href={`/products/${item.product.id}`}>{item.product.name}</Link>
                        </td>
                        <td className="muted">{item.product.expiry_date || '-'}</td>
                      </tr>
                    ))}
                  </tbody>
                </Table>
              </TableWrap>
            )}
            {!isPro ? <RestrictedHint /> : null}
          </CardContent>
        </Card>
      </section>

      <section className="columns-2">
        <Card>
          <CardHeader>
            <CardTitle>变更雷达列表</CardTitle>
            <CardDescription>按指标聚合的变更计数（前端中文显示）。</CardDescription>
          </CardHeader>
          <CardContent className="dashboard-compact">
          {!isPro ? (
            <ProLockedState text="雷达与到期风险等指标仅 Pro 可见。" />
          ) : radarRes.error ? (
            <ErrorState text={`雷达加载失败：${radarRes.error}`} />
          ) : !radarRes.data || radarRes.data.items.length === 0 ? (
            <EmptyState text="暂无雷达数据" />
          ) : (
            <TableWrap className="dashboard-compact-table">
              <Table className="dashboard-compact-table">
                <thead>
                  <tr>
                    <th>指标</th>
                    <th style={{ width: 90 }}>数值</th>
                  </tr>
                </thead>
                <tbody>
                  {radarRes.data.items.map((item) => (
                    <tr key={item.metric}>
                      <td title={item.metric}>{formatRadarMetric(item.metric)}</td>
                      <td>{item.value}</td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            </TableWrap>
          )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>日榜（后端聚合）</CardTitle>
            <CardDescription>新增高峰日与移除高峰日。</CardDescription>
          </CardHeader>
          <CardContent className="dashboard-compact">
          {!isPro ? (
            <ProLockedState text="日榜（聚合榜单）仅 Pro 可见。" />
          ) : rankingsRes.error ? (
            <ErrorState text={`榜单加载失败：${rankingsRes.error}`} />
          ) : !rankingsRes.data ? (
            <EmptyState text="暂无榜单" />
          ) : (
            <div className="dashboard-rankings-grid">
              <div>
                <div className="muted">新增高峰日</div>
                {rankingsRes.data.top_new_days.length === 0 ? (
                  <EmptyState text="暂无" />
                ) : (
                  <TableWrap className="dashboard-compact-table">
                    <Table className="dashboard-compact-table">
                      <thead>
                        <tr>
                          <th>日期</th>
                          <th style={{ width: 90 }}>新增</th>
                        </tr>
                      </thead>
                      <tbody>
                        {rankingsRes.data.top_new_days.map((x) => (
                          <tr key={x.metric_date}>
                            <td>
                              <Link href={`/search${qs({})}`}>{x.metric_date}</Link>
                            </td>
                            <td>{x.value}</td>
                          </tr>
                        ))}
                      </tbody>
                    </Table>
                  </TableWrap>
                )}
              </div>
              <div>
                <div className="muted">移除高峰日</div>
                {rankingsRes.data.top_removed_days.length === 0 ? (
                  <EmptyState text="暂无" />
                ) : (
                  <TableWrap className="dashboard-compact-table">
                    <Table className="dashboard-compact-table">
                      <thead>
                        <tr>
                          <th>日期</th>
                          <th style={{ width: 90 }}>移除</th>
                        </tr>
                      </thead>
                      <tbody>
                        {rankingsRes.data.top_removed_days.map((x) => (
                          <tr key={x.metric_date}>
                            <td>
                              <Link href={`/search${qs({ status: 'cancelled' })}`}>{x.metric_date}</Link>
                            </td>
                            <td>{x.value}</td>
                          </tr>
                        ))}
                      </tbody>
                    </Table>
                  </TableWrap>
                )}
              </div>
            </div>
          )}
          </CardContent>
        </Card>
      </section>
    </div>
  );
}
