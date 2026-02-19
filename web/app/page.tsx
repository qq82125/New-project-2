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
import { IVD_CATEGORY_ZH, LRI_RISK_ZH, RUN_STATUS_ZH, labelFrom } from '../constants/display';
import { getTopCompetitiveTracks, getTopGrowthCompanies, getTopRiskRegistrations } from '../lib/api/signals';
import { ApiHttpError } from '../lib/api/client';

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

type DashboardLriTopData = {
  total: number;
  limit: number;
  offset: number;
  items: Array<{
    product_id: string;
    product_name: string;
    risk_level: string;
    lri_norm: number;
    tte_days?: number | null;
    competitive_count?: number | null;
    gp_new_12m?: number | null;
    tte_score?: number | null;
    rh_score?: number | null;
    cd_score?: number | null;
    gp_score?: number | null;
    calculated_at?: string | null;
  }>;
};

type DashboardLriMapData = {
  total: number;
  limit: number;
  offset: number;
  items: Array<{
    methodology_id?: string | null;
    methodology_code?: string | null;
    methodology_name_cn?: string | null;
    ivd_category: string;
    total_count: number;
    high_risk_count: number;
    avg_lri_norm: number;
    gp_new_12m?: number | null;
  }>;
};

function lriBadgeVariant(level: string): 'success' | 'warning' | 'danger' | 'muted' {
  const v = String(level || '').toUpperCase();
  if (v === 'LOW') return 'success';
  if (v === 'MID') return 'warning';
  if (v === 'HIGH') return 'danger';
  if (v === 'CRITICAL') return 'danger';
  return 'muted';
}

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
        <Badge variant="muted">专业版</Badge>
        <Link className="ui-btn" href="/contact?intent=pro">
          联系开通
        </Link>
      </div>
    </div>
  );
}

function settledErrorText(err: unknown): string {
  if (err instanceof Error && err.message) return err.message;
  return '未知错误';
}

function settledIs404(err: unknown): boolean {
  return err instanceof ApiHttpError && err.status === 404;
}

function withTimeout<T>(promise: Promise<T>, ms: number, fallback: T): Promise<T> {
  return new Promise<T>((resolve) => {
    const timer = setTimeout(() => resolve(fallback), ms);
    promise
      .then((value) => {
        clearTimeout(timer);
        resolve(value);
      })
      .catch(() => {
        clearTimeout(timer);
        resolve(fallback);
      });
  });
}

export default async function DashboardPage({
  searchParams,
}: {
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
}) {
  const sp = (await searchParams) || {};
  function intParam(key: string, fallback: number): number {
    const raw = sp?.[key];
    const v = Array.isArray(raw) ? raw[0] : raw;
    const n = Number.parseInt(String(v ?? ''), 10);
    return Number.isFinite(n) && n >= 0 ? n : fallback;
  }

  const LRI_TOP_LIMIT = 10;
  const LRI_MAP_LIMIT = 30;
  const lriTopOffset = intParam('lri_top_offset', 0);
  const lriMapOffset = intParam('lri_map_offset', 0);
  const dashHref = (params: Record<string, string | number | undefined | null>) => `/${qs(params)}`;

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

  const [statusRes, summaryRes, trendRes, rankingsRes, radarRes, newProductRes, expiringRes, lriTopRes, lriMapRes] = await Promise.all([
    withTimeout(apiGet<StatusData>('/api/status'), 1200, { data: null, error: '请求超时', status: null }),
    withTimeout(apiGet<SummaryData>('/api/dashboard/summary?days=30'), 1200, { data: null, error: '请求超时', status: null }),
    withTimeout(apiGet<TrendData>('/api/dashboard/trend?days=30'), 1200, { data: null, error: '请求超时', status: null }),
    isPro
      ? withTimeout(apiGet<RankingsData>('/api/dashboard/rankings?days=30&limit=10'), 1200, { data: null, error: '请求超时', status: null })
      : Promise.resolve({ data: null, error: null }),
    isPro ? withTimeout(apiGet<RadarData>('/api/dashboard/radar'), 1200, { data: null, error: '请求超时', status: null }) : Promise.resolve({ data: null, error: null }),
    withTimeout(
      apiGet<SearchData>(`/api/search${qs({ page: 1, page_size: 20, sort_by: 'approved_date', sort_order: 'desc' })}`),
      1200,
      { data: null, error: '请求超时', status: null },
    ),
    isPro
      ? withTimeout(
          apiGet<SearchData>(`/api/search${qs({ page: 1, page_size: 20, sort_by: 'expiry_date', sort_order: 'asc' })}`),
          1200,
          { data: null, error: '请求超时', status: null },
        )
      : Promise.resolve({ data: null, error: null }),
    withTimeout(
      apiGet<DashboardLriTopData>(`/api/dashboard/lri/top${qs({ limit: LRI_TOP_LIMIT, offset: lriTopOffset })}`),
      1200,
      { data: null, error: '请求超时', status: null },
    ),
    withTimeout(
      apiGet<DashboardLriMapData>(`/api/dashboard/lri/map${qs({ limit: LRI_MAP_LIMIT, offset: lriMapOffset })}`),
      1200,
      { data: null, error: '请求超时', status: null },
    ),
  ]);
  const [topRiskRes, topCompetitiveRes, topGrowthRes] = await Promise.allSettled([
    withTimeout(getTopRiskRegistrations(), 1200, { items: [] }),
    withTimeout(getTopCompetitiveTracks(), 1200, { items: [] }),
    withTimeout(getTopGrowthCompanies(), 1200, { items: [] }),
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
              {labelFrom(RUN_STATUS_ZH, String(statusRes.data.latest_runs[0].status || '').toLowerCase())}
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
          <CardTitle>Signal 总览</CardTitle>
          <CardDescription>生命周期高风险、赛道拥挤度、企业扩张速度三栏榜单。</CardDescription>
        </CardHeader>
        <CardContent>
          <section className="columns-3">
            <Card>
              <CardHeader>
                <CardTitle>高风险生命周期证 Top10</CardTitle>
              </CardHeader>
              <CardContent className="grid">
                {topRiskRes.status === 'rejected' ? (
                  settledIs404(topRiskRes.reason) ? (
                    <EmptyState text="暂无数据" />
                  ) : (
                    <ErrorState text={`加载失败：${settledErrorText(topRiskRes.reason)}`} />
                  )
                ) : topRiskRes.value.items.length === 0 ? (
                  <EmptyState text="暂无数据" />
                ) : (
                  <TableWrap>
                    <Table>
                      <thead>
                        <tr>
                          <th>注册证</th>
                          <th style={{ width: 90 }}>level</th>
                          <th style={{ width: 100 }}>到期天数</th>
                        </tr>
                      </thead>
                      <tbody>
                        {topRiskRes.value.items.slice(0, 10).map((item) => (
                          <tr key={item.registration_no}>
                            <td>
                              <Link href={`/search${qs({ registration_no: item.registration_no })}`}>
                                {item.registration_no}
                              </Link>
                              <div className="muted">{item.company || '-'}</div>
                            </td>
                            <td>{item.level || '-'}</td>
                            <td>{item.days_to_expiry ?? '-'}</td>
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
                <CardTitle>拥挤赛道 Top10</CardTitle>
              </CardHeader>
              <CardContent className="grid">
                {topCompetitiveRes.status === 'rejected' ? (
                  settledIs404(topCompetitiveRes.reason) ? (
                    <EmptyState text="暂无数据" />
                  ) : (
                    <ErrorState text={`加载失败：${settledErrorText(topCompetitiveRes.reason)}`} />
                  )
                ) : topCompetitiveRes.value.items.length === 0 ? (
                  <EmptyState text="暂无数据" />
                ) : (
                  <TableWrap>
                    <Table>
                      <thead>
                        <tr>
                          <th>赛道</th>
                          <th style={{ width: 90 }}>level</th>
                          <th style={{ width: 100 }}>总量</th>
                          <th style={{ width: 110 }}>12m增速</th>
                        </tr>
                      </thead>
                      <tbody>
                        {topCompetitiveRes.value.items.slice(0, 10).map((item) => (
                          <tr key={item.track_id}>
                            <td>
                              <Link href={`/search${qs({ q: item.track_name })}`}>{item.track_name}</Link>
                            </td>
                            <td>{item.level || '-'}</td>
                            <td>{item.total_count ?? '-'}</td>
                            <td>{item.new_rate_12m ?? '-'}</td>
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
                <CardTitle>扩张最快企业 Top10</CardTitle>
              </CardHeader>
              <CardContent className="grid">
                {topGrowthRes.status === 'rejected' ? (
                  settledIs404(topGrowthRes.reason) ? (
                    <EmptyState text="暂无数据" />
                  ) : (
                    <ErrorState text={`加载失败：${settledErrorText(topGrowthRes.reason)}`} />
                  )
                ) : topGrowthRes.value.items.length === 0 ? (
                  <EmptyState text="暂无数据" />
                ) : (
                  <TableWrap>
                    <Table>
                      <thead>
                        <tr>
                          <th>企业</th>
                          <th style={{ width: 90 }}>level</th>
                          <th style={{ width: 110 }}>12m新增证</th>
                          <th style={{ width: 110 }}>12m新赛道</th>
                        </tr>
                      </thead>
                      <tbody>
                        {topGrowthRes.value.items.slice(0, 10).map((item) => (
                          <tr key={item.company_id}>
                            <td>
                              <Link href={`/companies/${encodeURIComponent(item.company_id)}`}>{item.company_name}</Link>
                            </td>
                            <td>{item.level || '-'}</td>
                            <td>{item.new_registrations_12m ?? '-'}</td>
                            <td>{item.new_tracks_12m ?? '-'}</td>
                          </tr>
                        ))}
                      </tbody>
                    </Table>
                  </TableWrap>
                )}
              </CardContent>
            </Card>
          </section>
        </CardContent>
      </Card>

      <section className="columns-2">
        <Card>
          <CardHeader>
            <CardTitle>高风险证 Top</CardTitle>
            <CardDescription>按 LRI 综合分倒序（分页 limit 生效）。</CardDescription>
          </CardHeader>
          <CardContent className="grid">
            {lriTopRes.error ? (
              <ErrorState text={`加载失败：${lriTopRes.error}`} />
            ) : !lriTopRes.data || lriTopRes.data.items.length === 0 ? (
              <EmptyState text="暂无 LRI 数据（可先运行 lri-compute 计算）。" />
            ) : (
              <TableWrap>
                <Table>
                  <thead>
                    <tr>
                      <th>产品</th>
                      <th style={{ width: 120 }}>风险等级</th>
                      {isPro ? <th style={{ width: 90 }}>综合分</th> : null}
                      {isPro ? <th style={{ width: 90 }}>TTE</th> : null}
                      {isPro ? <th style={{ width: 90 }}>竞争数</th> : null}
                      {isPro ? <th style={{ width: 110 }}>12月新增</th> : null}
                      {isPro ? <th style={{ width: 160 }}>分项(T/R/C/G)</th> : null}
                    </tr>
                  </thead>
                  <tbody>
                    {lriTopRes.data.items.map((it) => {
                      const risk = String(it.risk_level || '').toUpperCase();
                      const pct = Number(it.lri_norm || 0) * 100;
                      return (
                        <tr key={it.product_id}>
                          <td>
                            <Link href={`/search${qs({ q: it.product_name })}`}>{it.product_name}</Link>
                          </td>
                          <td>
                            <Badge variant={lriBadgeVariant(risk)}>{labelFrom(LRI_RISK_ZH, risk)}</Badge>
                          </td>
                          {isPro ? <td>{pct.toFixed(1)}%</td> : null}
                          {isPro ? <td>{it.tte_days ?? '-'}</td> : null}
                          {isPro ? <td>{it.competitive_count ?? '-'}</td> : null}
                          {isPro ? <td>{it.gp_new_12m ?? '-'}</td> : null}
                          {isPro ? (
                            <td className="muted">
                              {(it.tte_score ?? '-') + '/' + (it.rh_score ?? '-') + '/' + (it.cd_score ?? '-') + '/' + (it.gp_score ?? '-')}
                            </td>
                          ) : null}
                        </tr>
                      );
                    })}
                  </tbody>
                </Table>
              </TableWrap>
            )}
            {lriTopRes.data ? (
              <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between' }}>
                <span className="muted">
                  显示 {Math.min(LRI_TOP_LIMIT, lriTopRes.data.items.length)} 条，偏移 {lriTopOffset}，总数 {lriTopRes.data.total}
                </span>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  <Link
                    className={`ui-btn ui-btn--sm ui-btn--secondary ${lriTopOffset <= 0 ? 'is-disabled' : ''}`}
                    href={dashHref({
                      lri_top_offset: Math.max(0, lriTopOffset - LRI_TOP_LIMIT),
                      lri_map_offset: lriMapOffset,
                    })}
                    aria-disabled={lriTopOffset <= 0}
                    tabIndex={lriTopOffset <= 0 ? -1 : 0}
                  >
                    上一页
                  </Link>
                  <Link
                    className={`ui-btn ui-btn--sm ui-btn--secondary ${(lriTopOffset + LRI_TOP_LIMIT) >= lriTopRes.data.total ? 'is-disabled' : ''}`}
                    href={dashHref({
                      lri_top_offset: lriTopOffset + LRI_TOP_LIMIT,
                      lri_map_offset: lriMapOffset,
                    })}
                    aria-disabled={(lriTopOffset + LRI_TOP_LIMIT) >= lriTopRes.data.total}
                    tabIndex={(lriTopOffset + LRI_TOP_LIMIT) >= lriTopRes.data.total ? -1 : 0}
                  >
                    下一页
                  </Link>
                </div>
              </div>
            ) : null}
            {!isPro ? <RestrictedHint text="升级专业版查看 LRI 构成分项与关键输入（TTE、竞争数、近12月新增）。" /> : null}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>赛道风险地图</CardTitle>
            <CardDescription>维度：方法学 + IVD 分类。指标：平均风险、高风险数量、近12月新增。</CardDescription>
          </CardHeader>
          <CardContent className="grid">
            {lriMapRes.error ? (
              <ErrorState text={`加载失败：${lriMapRes.error}`} />
            ) : !lriMapRes.data || lriMapRes.data.items.length === 0 ? (
              <EmptyState text="暂无赛道风险数据" />
            ) : (
              <TableWrap>
                <Table>
                  <thead>
                    <tr>
                      <th>赛道</th>
                      <th style={{ width: 120 }}>平均风险</th>
                      <th style={{ width: 120 }}>高风险数</th>
                      {isPro ? <th style={{ width: 140 }}>12月新增证</th> : null}
                    </tr>
                  </thead>
                  <tbody>
                    {lriMapRes.data.items.map((it, idx) => {
                      const pct = Number(it.avg_lri_norm || 0) * 100;
                      const cat = labelFrom(IVD_CATEGORY_ZH, String(it.ivd_category || '')) || '未知';
                      const label = `${it.methodology_name_cn || it.methodology_code || '未映射'} · ${cat}`;
                      return (
                        <tr key={`${it.methodology_id || 'na'}:${it.ivd_category}:${idx}`}>
                          <td title={label}>{label}</td>
                          <td>{pct.toFixed(1)}%</td>
                          <td>{it.high_risk_count} / {it.total_count}</td>
                          {isPro ? <td>{it.gp_new_12m ?? '-'}</td> : null}
                        </tr>
                      );
                    })}
                  </tbody>
                </Table>
              </TableWrap>
            )}
            {lriMapRes.data ? (
              <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between' }}>
                <span className="muted">
                  显示 {Math.min(LRI_MAP_LIMIT, lriMapRes.data.items.length)} 条，偏移 {lriMapOffset}，总数 {lriMapRes.data.total}
                </span>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  <Link
                    className={`ui-btn ui-btn--sm ui-btn--secondary ${lriMapOffset <= 0 ? 'is-disabled' : ''}`}
                    href={dashHref({
                      lri_top_offset: lriTopOffset,
                      lri_map_offset: Math.max(0, lriMapOffset - LRI_MAP_LIMIT),
                    })}
                    aria-disabled={lriMapOffset <= 0}
                    tabIndex={lriMapOffset <= 0 ? -1 : 0}
                  >
                    上一页
                  </Link>
                  <Link
                    className={`ui-btn ui-btn--sm ui-btn--secondary ${(lriMapOffset + LRI_MAP_LIMIT) >= lriMapRes.data.total ? 'is-disabled' : ''}`}
                    href={dashHref({
                      lri_top_offset: lriTopOffset,
                      lri_map_offset: lriMapOffset + LRI_MAP_LIMIT,
                    })}
                    aria-disabled={(lriMapOffset + LRI_MAP_LIMIT) >= lriMapRes.data.total}
                    tabIndex={(lriMapOffset + LRI_MAP_LIMIT) >= lriMapRes.data.total ? -1 : 0}
                  >
                    下一页
                  </Link>
                </div>
              </div>
            ) : null}
            {!isPro ? <RestrictedHint text="升级专业版查看“近12月新增证数量”等赛道增长细节，用于竞争与增长判断。" /> : null}
          </CardContent>
        </Card>
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
            <ProLockedState text="雷达与到期风险等指标仅专业版可见。" />
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
            <ProLockedState text="日榜（聚合榜单）仅专业版可见。" />
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
