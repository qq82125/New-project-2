import { headers } from 'next/headers';
import { redirect } from 'next/navigation';
import Link from 'next/link';
import { EmptyState, ErrorState } from '../../components/States';
import { apiGet, qs } from '../../lib/api';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';

import { apiBase } from '../../lib/api-server';
import { getMe } from '../../lib/getMe';
import SearchExportActions from '../../components/search/SearchExportActions';
import SearchFiltersPanel from '../../components/search/SearchFiltersPanel';
import { SORT_BY_ZH, SORT_ORDER_ZH, STATUS_ZH, labelFrom } from '../../constants/display';
import PaginationControls from '../../components/PaginationControls';
import { getSearchSignalsBatch, type SearchSignalItem } from '../../lib/api/signals';

type SearchParams = {
  q?: string;
  company?: string;
  reg_no?: string;
  registration_no?: string;
  status?: string;
  page?: string;
  page_size?: string;
  sort_by?: 'updated_at' | 'approved_date' | 'expiry_date' | 'name';
  sort_order?: 'asc' | 'desc';
  include_pending?: string;
  include_unverified?: string;
};

type SearchData = {
  total: number;
  page: number;
  page_size: number;
  sort_by: string;
  sort_order: string;
  items: Array<{
    product: {
  id: string;
  name: string;
  reg_no?: string | null;
  udi_di?: string | null;
  status: string;
  company?: { id: string; name: string } | null;
  expiry_date?: string | null;
  is_stub?: boolean | null;
  source_hint?: string | null;
  verified_by_nmpa?: boolean | null;
};
  }>;
};

export default async function SearchPage({ searchParams }: { searchParams: Promise<SearchParams> }) {
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
  let canExport = false;
  try {
    const body = (await meRes.json()) as any;
    canExport = Boolean(body?.data?.entitlements?.can_export);
  } catch {
    canExport = false;
  }

  const params = await searchParams;
  const page = Number(params.page || '1');
  const pageSize = Number(params.page_size || '20');
  const sortBy = params.sort_by || 'updated_at';
  const sortOrder = params.sort_order || 'desc';
  const includePending =
    params.include_pending === '1' ||
    params.include_pending === 'true' ||
    params.include_unverified === '1' ||
    params.include_unverified === 'true';
  const regNo = params.reg_no || params.registration_no;

  const query = qs({
    q: params.q,
    company: params.company,
    reg_no: regNo,
    status: params.status,
    page,
    page_size: pageSize,
    sort_by: sortBy,
    sort_order: sortOrder,
    include_unverified: includePending ? 'true' : undefined,
  });

  const res = await apiGet<SearchData>(`/api/search${query}`);
  const exportHref = `/api/export/search.csv${qs({ q: params.q, company: params.company, reg_no: regNo })}`;
  const visibleItems = (res.data?.items || []).slice(0, isPro ? undefined : 10);
  const registrationNos = visibleItems.map((x) => x.product.reg_no || '').filter(Boolean) as string[];
  let signalMap = new Map<string, SearchSignalItem>();
  let signalError: string | null = null;
  try {
    const signalRes = await getSearchSignalsBatch(registrationNos);
    signalMap = new Map(signalRes.items.map((x) => [x.registration_no, x]));
  } catch (err) {
    signalError = err instanceof Error ? err.message : '未知错误';
    signalMap = new Map();
  }

  return (
    <div className="grid">
      <Card>
        <CardHeader>
          <CardTitle>搜索</CardTitle>
          <CardDescription>按关键词、企业、注册证号等筛选产品。</CardDescription>
        </CardHeader>
        <CardContent>
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center', marginBottom: 10 }}>
            <SearchExportActions canExport={canExport} exportHref={exportHref} />
          </div>
          <SearchFiltersPanel
            initial={{
              q: params.q || '',
              company: params.company || '',
              reg_no: regNo || '',
              status: params.status || '',
              sort_by: sortBy,
              sort_order: sortOrder,
              include_pending: includePending,
            }}
          />
        </CardContent>
      </Card>

      {res.error ? (
        <ErrorState text={`搜索失败：${res.error}`} />
      ) : !res.data ? (
        <EmptyState text="暂无结果" />
      ) : (
        <>
          {(() => {
            const totalPages = Math.max(1, Math.ceil((res.data?.total || 0) / Math.max(1, pageSize)));
            return (
          <Card>
            <CardContent style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
              <Badge variant="muted">共 {res.data.total} 条</Badge>
              <span className="muted">
                第 {res.data.page} / {totalPages} 页（每页 {res.data.page_size} 条） / 排序：{labelFrom(SORT_BY_ZH, res.data.sort_by)}（{labelFrom(SORT_ORDER_ZH, res.data.sort_order)}）
              </span>
            </CardContent>
          </Card>
            );
          })()}
          {res.data.items.length === 0 ? (
            <EmptyState text="暂无匹配结果" />
          ) : (
            <div className="list">
              {visibleItems.map((item) => {
                const regNo = item.product.reg_no || '';
                const signal = regNo ? signalMap.get(regNo) : undefined;
                const mainHref = regNo ? `/registrations/${encodeURIComponent(regNo)}` : `/products/${item.product.id}`;
                return (
                <Card key={item.product.id}>
                  <CardHeader>
                    <CardTitle>
                      <Link href={mainHref}>{item.product.name}</Link>
                    </CardTitle>
                    <CardDescription>检索结果</CardDescription>
                  </CardHeader>
                  <CardContent className="grid">
                    <div className="controls">
                      <div><span className="muted">产品名：</span>{item.product.name || '-'}</div>
                      <div><span className="muted">企业名：</span>{item.product.company?.name || '-'}</div>
                      <div><span className="muted">注册证号：</span>{item.product.reg_no || '-'}</div>
                      <div><span className="muted">状态：</span>{labelFrom(STATUS_ZH, item.product.status) || '-'}</div>
                      <div><span className="muted">失效日期：</span>{item.product.expiry_date || '-'}</div>
                      <div><span className="muted">UDI-DI：</span>{item.product.udi_di || '-'}</div>
                    </div>
                    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
                      {item.product.is_stub === true ? <Badge variant="warning">stub</Badge> : null}
                      {item.product.verified_by_nmpa === true ? <Badge variant="success">NMPA verified</Badge> : null}
                    </div>
                    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
                      {!regNo ? (
                        <Badge variant="muted">无注册证锚点</Badge>
                      ) : (
                        <>
                          {signal?.lifecycle_level ? <Badge variant="muted">生命周期: {signal.lifecycle_level}</Badge> : null}
                          {signal?.track_level ? <Badge variant="muted">竞争: {signal.track_level}</Badge> : null}
                          {signal?.company_level ? <Badge variant="muted">扩张: {signal.company_level}</Badge> : null}
                          {!signal?.lifecycle_level && !signal?.track_level && !signal?.company_level ? (
                            <Badge variant="muted">信号暂无</Badge>
                          ) : null}
                        </>
                      )}
                    </div>
                    {signal?.factors_summary ? <div className="muted">{signal.factors_summary}</div> : null}
                    {signalError ? <div className="muted">信号加载降级：{signalError}</div> : null}
                    <div>
                      <span className="muted">企业:</span>{' '}
                      {item.product.company ? (
                        <Link href={`/companies/${item.product.company.id}`}>{item.product.company.name}</Link>
                      ) : (
                        '-'
                      )}
                    </div>
                    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
                      {regNo ? (
                        <Link className="ui-btn ui-btn--sm ui-btn--default" href={`/registrations/${encodeURIComponent(regNo)}`}>
                          查看注册证
                        </Link>
                      ) : null}
                      <Link className="ui-btn ui-btn--sm ui-btn--secondary" href={`/products/${item.product.id}`}>
                        查看产品
                      </Link>
                    </div>
                  </CardContent>
                </Card>
              );
              })}
            </div>
          )}

          <Card>
            <CardContent style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
              <PaginationControls
                basePath="/search"
                params={{
                  q: params.q,
                  company: params.company,
                  reg_no: regNo,
                  status: params.status,
                  sort_by: sortBy,
                  sort_order: sortOrder,
                  include_pending: includePending ? '1' : undefined,
                }}
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
