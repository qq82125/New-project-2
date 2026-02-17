import Link from 'next/link';
import { headers } from 'next/headers';
import { redirect } from 'next/navigation';

import { Badge } from '../../../components/ui/badge';
import { Button } from '../../../components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../../components/ui/card';
import { Input } from '../../../components/ui/input';
import { EmptyState, ErrorState } from '../../../components/States';
import { apiGet, qs } from '../../../lib/api';
import { apiBase } from '../../../lib/api-server';
import { getMe } from '../../../lib/getMe';
import ProUpgradeHint from '../../../components/plan/ProUpgradeHint';
import { PRO_TRIAL_HREF, PRO_COPY } from '../../../constants/pro';
import PaginationControls from '../../../components/PaginationControls';

type Params = { q?: string; page?: string; page_size?: string };
type TrackingList = {
  total: number;
  page: number;
  page_size: number;
  items: Array<{
    company_id: string;
    company_name: string;
    country?: string | null;
    total_products: number;
    active_products: number;
    last_product_updated_at?: string | null;
  }>;
};

function formatDateTime(value?: string | null): string {
  if (!value) return '-';
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) {
    return value.length > 16 ? value.slice(0, 16).replace('T', ' ') : value;
  }
  return d
    .toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      hour12: false,
    })
    .replace(/\//g, '-');
}

export default async function CompanyTrackingPage({ searchParams }: { searchParams: Promise<Params> }) {
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
  const page = Number(params.page || '1');
  const pageSize = Number(params.page_size || '30');
  const query = qs({ q: params.q, page, page_size: pageSize });

  const res = isPro ? await apiGet<TrackingList>(`/api/company-tracking${query}`) : { data: null, error: null };
  const totalPages = Math.max(1, Math.ceil(((res.data?.total || 0) as number) / Math.max(1, pageSize)));

  return (
    <div className="grid">
      <Card>
        <CardHeader>
          <CardTitle>企业维度追踪</CardTitle>
          <CardDescription>按企业聚合查看 IVD 产品规模、活跃状态和最近更新。</CardDescription>
        </CardHeader>
        <CardContent>
          <form className="controls" method="GET">
            <Input name="q" defaultValue={params.q} placeholder="输入企业名称关键词" />
            <Input name="page_size" defaultValue={String(pageSize)} placeholder="每页数量" inputMode="numeric" />
            <Button type="submit">查询</Button>
          </form>
        </CardContent>
      </Card>

      {!isPro ? (
        <Card>
          <CardContent>
            <ProUpgradeHint text={PRO_COPY.banner.free_subtitle} ctaHref={PRO_TRIAL_HREF} />
          </CardContent>
        </Card>
      ) : res.error ? (
        <ErrorState text={`加载失败：${res.error}`} />
      ) : !res.data ? (
        <EmptyState text="暂无数据" />
      ) : (
        <>
          <Card>
            <CardContent style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
              <Badge variant="muted">共 {res.data.total} 家企业</Badge>
              <span className="muted">
                第 {res.data.page} / {totalPages} 页（每页 {res.data.page_size} 条）
              </span>
            </CardContent>
          </Card>

          {res.data.items.length === 0 ? (
            <EmptyState text="暂无匹配企业" />
          ) : (
            <div className="list">
              {res.data.items.map((it) => (
                <Card key={it.company_id}>
                  <CardHeader>
                    <CardTitle>
                      <Link href={`/companies/tracking/${it.company_id}`}>{it.company_name}</Link>
                    </CardTitle>
                    <CardDescription>国家/地区：{it.country || '-'}</CardDescription>
                  </CardHeader>
                  <CardContent style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
                    <Badge variant="muted">产品总数: {it.total_products}</Badge>
                    <Badge variant="muted">有效产品: {it.active_products}</Badge>
                    <Badge variant="muted">最近更新: {formatDateTime(it.last_product_updated_at)}</Badge>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}

          <Card>
            <CardContent style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
              <PaginationControls
                basePath="/companies/tracking"
                params={{ q: params.q }}
                page={page}
                pageSize={pageSize}
                total={res.data.total}
              />
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
