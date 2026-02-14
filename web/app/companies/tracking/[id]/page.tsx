import Link from 'next/link';
import { headers } from 'next/headers';
import { redirect } from 'next/navigation';

import { Badge } from '../../../../components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../../../components/ui/card';
import { EmptyState, ErrorState } from '../../../../components/States';
import { apiGet, qs } from '../../../../lib/api';
import { apiBase } from '../../../../lib/api-server';
import { getMe } from '../../../../lib/getMe';
import ProUpgradeHint from '../../../../components/plan/ProUpgradeHint';
import { PRO_COPY, PRO_TRIAL_HREF } from '../../../../constants/pro';
import { CHANGE_TYPE_ZH, IVD_CATEGORY_ZH, STATUS_ZH, labelFrom } from '../../../../constants/display';
import PaginationControls from '../../../../components/PaginationControls';

type DetailData = {
  company: { id: string; name: string; country?: string | null };
  stats: {
    days: number;
    total_products: number;
    active_products: number;
    expired_products: number;
    cancelled_products: number;
    last_product_updated_at?: string | null;
    changes_total: number;
    changes_by_type: Record<string, number>;
  };
  recent_changes: Array<{
    id: number;
    change_type: string;
    change_date?: string | null;
    product: {
      id: string;
      name: string;
      udi_di?: string | null;
      reg_no?: string | null;
      status: string;
      ivd_category?: string | null;
    };
  }>;
  recent_changes_total: number;
  page: number;
  page_size: number;
};

export default async function CompanyTrackingDetailPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ days?: string; page?: string; page_size?: string; limit?: string }>;
}) {
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

  const { id } = await params;
  const sp = await searchParams;
  const days = Number(sp.days || '30');
  const page = Math.max(1, Number(sp.page || '1'));
  const pageSize = Math.max(1, Number(sp.page_size || sp.limit || '30'));
  const res = isPro
    ? await apiGet<DetailData>(`/api/company-tracking/${id}${qs({ days, page, page_size: pageSize })}`)
    : { data: null, error: null };
  const totalPages = Math.max(
    1,
    Math.ceil(Number(res.data?.recent_changes_total || 0) / Math.max(1, Number(res.data?.page_size || pageSize))),
  );

  return (
    <div className="grid">
      {!isPro ? (
        <Card>
          <CardContent>
            <ProUpgradeHint text={PRO_COPY.banner.free_subtitle} ctaHref={PRO_TRIAL_HREF} />
          </CardContent>
        </Card>
      ) : res.error ? (
        <ErrorState text={`加载失败：${res.error}`} />
      ) : !res.data ? (
        <EmptyState text="企业追踪数据不存在" />
      ) : (
        <>
          <Card>
            <CardHeader>
              <CardTitle>{res.data.company.name}</CardTitle>
              <CardDescription>企业维度追踪（近 {res.data.stats.days} 天）</CardDescription>
            </CardHeader>
            <CardContent style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
              <Badge variant="muted">国家/地区: {res.data.company.country || '-'}</Badge>
              <Badge variant="muted">产品总数: {res.data.stats.total_products}</Badge>
              <Badge variant="muted">有效: {res.data.stats.active_products}</Badge>
              <Badge variant="muted">过期: {res.data.stats.expired_products}</Badge>
              <Badge variant="muted">注销: {res.data.stats.cancelled_products}</Badge>
              <Badge variant="muted">变化总量: {res.data.stats.changes_total}</Badge>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>最近变化</CardTitle>
              <CardDescription>按时间倒序展示该企业产品变化</CardDescription>
            </CardHeader>
            <CardContent className="grid">
              <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
                <Badge variant="muted">共 {res.data.recent_changes_total} 条变化</Badge>
                <span className="muted">
                  第 {res.data.page} / {totalPages} 页（每页 {res.data.page_size} 条）
                </span>
              </div>
              {res.data.recent_changes.length === 0 ? (
                <EmptyState text="暂无变化记录" />
              ) : (
                <div className="list">
                  {res.data.recent_changes.map((x) => (
                    <Card key={x.id}>
                      <CardHeader>
                        <CardTitle>
                          <Link href={`/products/${x.product.id}`}>{x.product.name}</Link>
                        </CardTitle>
                        <CardDescription>
                          变化类型: {labelFrom(CHANGE_TYPE_ZH, x.change_type)} · 时间: {x.change_date || '-'}
                        </CardDescription>
                      </CardHeader>
                      <CardContent style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
                        <Badge variant="muted">UDI-DI: {x.product.udi_di || '-'}</Badge>
                        <Badge variant="muted">注册证号: {x.product.reg_no || '-'}</Badge>
                        <Badge variant="muted">状态: {labelFrom(STATUS_ZH, x.product.status)}</Badge>
                        <Badge variant="muted">IVD分类: {labelFrom(IVD_CATEGORY_ZH, x.product.ivd_category)}</Badge>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardContent style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
              <PaginationControls
                basePath={`/companies/tracking/${id}`}
                params={{ days }}
                page={res.data.page}
                pageSize={res.data.page_size}
                total={res.data.recent_changes_total}
              />
              <Link href="/companies/tracking">返回企业维度追踪列表</Link>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
