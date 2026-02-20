import { headers } from 'next/headers';
import { redirect } from 'next/navigation';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { EmptyState, ErrorState } from '../components/States';
import { apiBase } from '../lib/api-server';
import { apiGet } from '../lib/api';
import { buildSearchUrl } from '../lib/search-filters';
import KpiCard, { type KpiCardItem } from '../components/dashboard/KpiCard';
import SignalInbox from '../components/dashboard/SignalInbox';
import TrackGrid, { type TrackGridItem } from '../components/dashboard/TrackGrid';
import DashboardTopbar from '../components/dashboard/DashboardTopbar';
import TrendEntry from '../components/dashboard/TrendEntry';
import { DASHBOARD_TRACK_SEEDS } from '../constants/tracks';
import type { UnifiedTableRow } from '../components/table/columns';
import type { UnifiedBadgeToken } from '../components/common/UnifiedBadge';
import {
  getTopCompetitiveTracks,
  getTopGrowthCompanies,
  getTopRiskRegistrations,
  type TopCompetitiveTrackItem,
  type TopGrowthCompanyItem,
  type TopRiskRegistrationItem,
} from '../lib/api/signals';

type SummaryData = {
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

function sumLastDays(
  rows: TrendData['items'],
  key: 'new_products' | 'updated_products' | 'cancelled_products',
  days: number,
): number {
  return rows.slice(-days).reduce((sum, row) => sum + Number(row[key] || 0), 0);
}

function asArray<T>(value: unknown): T[] {
  return Array.isArray(value) ? (value as T[]) : [];
}

function badge(kind: UnifiedBadgeToken['kind'], value: string): UnifiedBadgeToken {
  return { kind, value };
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

  const [summaryRes, trendRes, topRiskRes, topCompetitiveRes, topGrowthRes] = await Promise.all([
    withTimeout(apiGet<SummaryData>('/api/dashboard/summary?days=30'), 1200, { data: null, error: '请求超时', status: null }),
    withTimeout(apiGet<TrendData>('/api/dashboard/trend?days=30'), 1200, { data: null, error: '请求超时', status: null }),
    Promise.resolve(withTimeout(getTopRiskRegistrations(), 1200, { items: [] as TopRiskRegistrationItem[] }))
      .then((value) => ({ status: 'fulfilled', value } as const))
      .catch((reason) => ({ status: 'rejected', reason } as const)),
    Promise.resolve(withTimeout(getTopCompetitiveTracks(), 1200, { items: [] as TopCompetitiveTrackItem[] }))
      .then((value) => ({ status: 'fulfilled', value } as const))
      .catch((reason) => ({ status: 'rejected', reason } as const)),
    Promise.resolve(withTimeout(getTopGrowthCompanies(), 1200, { items: [] as TopGrowthCompanyItem[] }))
      .then((value) => ({ status: 'fulfilled', value } as const))
      .catch((reason) => ({ status: 'rejected', reason } as const)),
  ]);

  const trendRows = trendRes.data?.items || [];
  const kpiItems: KpiCardItem[] = [
    {
      label: '30天新增',
      value: Number(summaryRes.data?.total_new || 0),
      hint: '按新增变更下钻',
      href: buildSearchUrl({ change_type: 'new', date_range: '30d', sort: 'recency' }),
    },
    {
      label: '30天更新',
      value: Number(summaryRes.data?.total_updated || 0),
      hint: '按更新变更下钻',
      href: buildSearchUrl({ change_type: 'update', date_range: '30d', sort: 'recency' }),
    },
    {
      label: '30天注销',
      value: Number(summaryRes.data?.total_removed || 0),
      hint: '按注销变更下钻',
      href: buildSearchUrl({ change_type: 'cancel', date_range: '30d', sort: 'recency' }),
    },
    {
      label: '7天新增',
      value: sumLastDays(trendRows, 'new_products', 7),
      hint: '最近7天窗口',
      href: buildSearchUrl({ change_type: 'new', date_range: '7d', sort: 'recency' }),
    },
    {
      label: '活跃订阅',
      value: Number(summaryRes.data?.latest_active_subscriptions || 0),
      hint: '查看全量列表',
      href: buildSearchUrl({ date_range: '30d', sort: 'recency' }),
    },
  ];

  const riskItems = topRiskRes.status === 'fulfilled' ? asArray<TopRiskRegistrationItem>(topRiskRes.value.items).slice(0, 4) : [];
  const competitiveItems = topCompetitiveRes.status === 'fulfilled' ? asArray<TopCompetitiveTrackItem>(topCompetitiveRes.value.items).slice(0, 3) : [];
  const growthItems = topGrowthRes.status === 'fulfilled' ? asArray<TopGrowthCompanyItem>(topGrowthRes.value.items).slice(0, 3) : [];

  const inboxRows: UnifiedTableRow[] = [
    {
      id: 'new-7d',
      product_name: '近7天新增产品',
      company_name: '新增信号入口',
      registration_no: '-',
      status: '-',
      expiry_date: '-',
      udi_di: '-',
      badges: [badge('change', 'new')],
      detail_href: buildSearchUrl({ change_type: 'new', date_range: '7d', sort: 'recency' }),
    },
    {
      id: 'update-7d',
      product_name: '近7天更新产品',
      company_name: '更新信号入口',
      registration_no: '-',
      status: '-',
      expiry_date: '-',
      udi_di: '-',
      badges: [badge('change', 'update')],
      detail_href: buildSearchUrl({ change_type: 'update', date_range: '7d', sort: 'recency' }),
    },
    {
      id: 'cancel-30d',
      product_name: '近30天注销产品',
      company_name: '注销信号入口',
      registration_no: '-',
      status: '-',
      expiry_date: '-',
      udi_di: '-',
      badges: [badge('change', 'cancel')],
      detail_href: buildSearchUrl({ change_type: 'cancel', date_range: '30d', sort: 'recency' }),
    },
    ...riskItems.map((item, idx) => ({
      id: `risk-${idx}`,
      product_name: `高风险证：${item.registration_no}`,
      company_name: item.company || '高风险生命周期证',
      registration_no: item.registration_no || '-',
      status: '-',
      expiry_date: item.days_to_expiry != null ? `TTE ${item.days_to_expiry}d` : '-',
      udi_di: '-',
      badges: [badge('risk', 'high')],
      detail_href: buildSearchUrl({ q: item.registration_no, risk: 'high', date_range: '30d', sort: 'risk' }),
    })),
    ...competitiveItems.map((item, idx) => ({
      id: `comp-${idx}`,
      product_name: `拥挤赛道：${item.track_name}`,
      company_name: '竞争强度入口',
      registration_no: '-',
      status: '-',
      expiry_date: '-',
      udi_di: '-',
      badges: [
        badge('track', item.track_name || '-'),
        badge('risk', item.level || 'medium'),
      ],
      detail_href: buildSearchUrl({ track: item.track_name, date_range: '12m', sort: 'competition' }),
    })),
    ...growthItems.map((item, idx) => ({
      id: `growth-${idx}`,
      product_name: `扩张企业：${item.company_name}`,
      company_name: '增长入口',
      registration_no: '-',
      status: '-',
      expiry_date: '-',
      udi_di: '-',
      badges: [badge('risk', item.level || 'medium')],
      detail_href: buildSearchUrl({ company: item.company_name, date_range: '12m', sort: 'competition' }),
    })),
  ].slice(0, 12);

  const dynamicTrackNames = competitiveItems.map((x) => x.track_name).filter(Boolean);
  const staticTracks = DASHBOARD_TRACK_SEEDS.map((seed) => ({
    id: seed.id,
    name: seed.name,
    description: seed.description,
  }));
  const dynamicTracks = dynamicTrackNames.map((name, idx) => ({
    id: `dyn-${idx}`,
    name,
    description: '来自近12月竞争赛道',
  }));
  const dedup = new Map<string, { id: string; name: string; description: string }>();
  [...dynamicTracks, ...staticTracks].forEach((t) => {
    if (!dedup.has(t.name)) dedup.set(t.name, t);
  });
  const trackItems: TrackGridItem[] = Array.from(dedup.values())
    .slice(0, 9)
    .map((t) => ({
      id: t.id,
      name: t.name,
      description: t.description,
      href: buildSearchUrl({ track: t.name, sort: 'competition', date_range: '30d' }),
    }));

  const hasDataError = summaryRes.error && trendRes.error;

  return (
    <div className="grid" style={{ gap: 14 }}>
      <Card>
        <CardHeader>
          <CardTitle>Dashboard Entry</CardTitle>
          <CardDescription>全局入口：KPI、今日信号收件箱、赛道入口。所有卡片均可钻取至 Search。</CardDescription>
        </CardHeader>
        <CardContent>
          <DashboardTopbar />
        </CardContent>
      </Card>

      {hasDataError ? (
        <ErrorState text={`仪表盘加载失败：${summaryRes.error || trendRes.error}`} />
      ) : (
        <>
          <section className="kpis">
            {kpiItems.map((item) => (
              <KpiCard key={item.label} {...item} />
            ))}
          </section>
          <TrendEntry items={trendRows} />
          <SignalInbox rows={inboxRows} />
          {trackItems.length === 0 ? <EmptyState text="暂无赛道入口" /> : <TrackGrid tracks={trackItems} />}
        </>
      )}
    </div>
  );
}
