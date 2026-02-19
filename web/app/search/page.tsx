import { headers } from 'next/headers';
import { redirect } from 'next/navigation';
import { Suspense } from 'react';
import { EmptyState, ErrorState } from '../../components/States';
import { apiGet, qs } from '../../lib/api';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';
import { Skeleton } from '../../components/ui/skeleton';

import { apiBase } from '../../lib/api-server';
import SearchExportActions from '../../components/search/SearchExportActions';
import SearchFiltersPanel from '../../components/search/SearchFiltersPanel';
import FilterChips from '../../components/search/FilterChips';
import { STATUS_ZH, labelFrom } from '../../constants/display';
import PaginationControls from '../../components/PaginationControls';
import { getSearchSignalsBatch, type SearchSignalItem } from '../../lib/api/signals';
import { buildSearchUrl, parseSearchUrl, type SearchFilters } from '../../lib/search-filters';
import UnifiedTable from '../../components/table/UnifiedTable';
import type { UnifiedTableRow } from '../../components/table/columns';

type SearchParams = Record<string, string | string[] | undefined>;

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

function toUrlSearchParams(params: SearchParams): URLSearchParams {
  const sp = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (Array.isArray(value)) {
      value.forEach((v) => {
        if (v != null && v !== '') sp.append(key, String(v));
      });
      return;
    }
    if (value != null && value !== '') sp.set(key, String(value));
  });
  return sp;
}

function parsePage(raw: string | null | undefined, fallback: number): number {
  const n = Number.parseInt(String(raw || ''), 10);
  return Number.isFinite(n) && n > 0 ? n : fallback;
}

function mapFiltersToApi(filters: SearchFilters): {
  q?: string;
  company?: string;
  status?: string;
  sort_by: 'updated_at' | 'approved_date' | 'expiry_date' | 'name';
  sort_order: 'asc' | 'desc';
} {
  let status = filters.status || undefined;
  if (!status && filters.change_type === 'cancel') {
    status = 'cancelled';
  }
  // TODO(PR0): `track/change_type(new|update)/date_range/risk/sort(risk|lri|competition)` are preserved in URL for sharing,
  // but current backend /api/search does not support them yet.
  let sort_by: 'updated_at' | 'approved_date' | 'expiry_date' | 'name' = 'approved_date';
  let sort_order: 'asc' | 'desc' = 'desc';
  if (filters.sort === 'recency') {
    sort_by = 'approved_date';
    sort_order = 'desc';
  }
  return {
    q: filters.q || undefined,
    company: filters.company || undefined,
    status,
    sort_by,
    sort_order,
  };
}

function buildPagedSearchUrl(filters: SearchFilters, page: number, pageSize: number): string {
  const href = buildSearchUrl(filters);
  const query = href.split('?')[1] || '';
  const sp = new URLSearchParams(query);
  sp.set('page', String(page));
  sp.set('page_size', String(pageSize));
  return `/search?${sp.toString()}`;
}

function SearchResultsFallback() {
  return (
    <div className="grid">
      <Card>
        <CardContent style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
          <Skeleton width={96} height={20} />
          <Skeleton width={220} height={20} />
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>结果列表</CardTitle>
        </CardHeader>
        <CardContent className="grid">
          {Array.from({ length: 8 }).map((_, i) => (
            <Skeleton key={i} height={34} />
          ))}
        </CardContent>
      </Card>
    </div>
  );
}

async function SearchResultsSection({
  filters,
  page,
  pageSize,
  isPro,
  currentSearchHref,
}: {
  filters: SearchFilters;
  page: number;
  pageSize: number;
  isPro: boolean;
  currentSearchHref: string;
}) {
  const apiMapped = mapFiltersToApi(filters);
  const query = qs({
    q: apiMapped.q,
    company: apiMapped.company,
    status: apiMapped.status,
    page,
    page_size: pageSize,
    sort_by: apiMapped.sort_by,
    sort_order: apiMapped.sort_order,
  });

  const res = await withTimeout(
    apiGet<SearchData>(`/api/search${query}`),
    10000,
    { data: null, error: '请求超时', status: null } as { data: SearchData | null; error: string | null; status?: number | null },
  );

  if (res.error) {
    return <ErrorState text={`搜索失败：${res.error}`} />;
  }
  if (!res.data) {
    return <EmptyState text="暂无结果" />;
  }

  const visibleItems = (res.data.items || []).slice(0, isPro ? undefined : 10);
  const hasFilter = Boolean(filters.q || filters.track || filters.company || filters.status || filters.change_type || filters.date_range || filters.risk);
  const registrationNos = hasFilter ? (visibleItems.map((x) => x.product.reg_no || '').filter(Boolean).slice(0, 8) as string[]) : [];
  let signalMap = new Map<string, SearchSignalItem>();
  let signalError: string | null = null;
  if (registrationNos.length > 0) {
    try {
      const signalRes = await withTimeout(getSearchSignalsBatch(registrationNos), 900, { items: [] });
      signalMap = new Map(signalRes.items.map((x) => [x.registration_no, x]));
    } catch (err) {
      signalError = err instanceof Error ? err.message : '未知错误';
      signalMap = new Map();
    }
  }

  const tableRows: UnifiedTableRow[] = visibleItems.map((item) => {
    const regNo = item.product.reg_no || '';
    const signal = regNo ? signalMap.get(regNo) : undefined;
    const back = encodeURIComponent(currentSearchHref);
    const detailHref = regNo
      ? `/registrations/${encodeURIComponent(regNo)}?back=${back}`
      : `/products/${item.product.id}?back=${back}`;
    const badges: UnifiedTableRow['badges'] = [];
    if (item.product.is_stub === true) badges.push({ kind: 'custom', value: 'stub' });
    if (item.product.verified_by_nmpa === true) badges.push({ kind: 'custom', value: 'NMPA verified' });
    if (signal?.lifecycle_level) badges.push({ kind: 'risk', value: `lifecycle:${signal.lifecycle_level}` });
    if (signal?.track_level) badges.push({ kind: 'risk', value: `track:${signal.track_level}` });
    if (signal?.company_level) badges.push({ kind: 'risk', value: `company:${signal.company_level}` });
    return {
      id: item.product.id,
      product_name: item.product.name || '-',
      company_name: item.product.company?.name || '-',
      registration_no: regNo || '-',
      status: labelFrom(STATUS_ZH, item.product.status) || item.product.status || '-',
      expiry_date: item.product.expiry_date || '-',
      udi_di: item.product.udi_di || '-',
      badges,
      detail_href: detailHref,
      action: {
        type: 'benchmark',
        registration_no: regNo || '',
        set_id: 'my-benchmark',
        label: regNo ? undefined : 'N/A',
        disabled: !regNo,
      },
    };
  });

  const totalPages = Math.max(1, Math.ceil((res.data.total || 0) / Math.max(1, pageSize)));

  return (
    <>
      <Card>
        <CardContent style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
          <Badge variant="muted">共 {res.data.total} 条</Badge>
          <span className="muted">
            第 {res.data.page} / {totalPages} 页（每页 {res.data.page_size} 条）
          </span>
        </CardContent>
      </Card>

      {res.data.items.length === 0 ? (
        <EmptyState text="暂无匹配结果" />
      ) : (
        <Card>
          <CardHeader>
            <CardTitle>结果列表</CardTitle>
            <CardDescription>
              统一列顺序与 Badge 规则。{signalError ? `信号加载降级：${signalError}` : '点击行进入详情。'}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <UnifiedTable
              rows={tableRows}
              columns={[
                'product_name',
                'company_name',
                'registration_no',
                'status',
                'expiry_date',
                'udi_di',
                'badges',
                'actions',
              ]}
            />
          </CardContent>
        </Card>
      )}

      <Card>
        <CardContent style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
          <PaginationControls
            basePath="/search"
            params={{
              ...filters,
            }}
            page={page}
            pageSize={pageSize}
            total={res.data.total}
            buildHref={(targetPage, targetPageSize) => buildPagedSearchUrl(filters, targetPage, targetPageSize)}
          />
        </CardContent>
      </Card>
    </>
  );
}

export default async function SearchPage({ searchParams }: { searchParams: Promise<SearchParams> }) {
  const API_BASE = apiBase();
  const cookie = (await headers()).get('cookie') || '';
  const meRes = await fetch(`${API_BASE}/api/auth/me`, {
    method: 'GET',
    headers: cookie ? { cookie } : undefined,
    cache: 'no-store',
  });
  if (meRes.status === 401) redirect('/login');

  let isPro = false;
  let canExport = false;
  try {
    const body = (await meRes.json()) as any;
    isPro = Boolean(body?.data?.plan?.is_pro || body?.data?.plan?.is_admin);
    canExport = Boolean(body?.data?.entitlements?.can_export);
  } catch {
    isPro = false;
    canExport = false;
  }

  const paramsObj = await searchParams;
  const urlParams = toUrlSearchParams(paramsObj);
  const filters = parseSearchUrl(urlParams);
  const page = parsePage(urlParams.get('page'), 1);
  const pageSize = parsePage(urlParams.get('page_size'), 10);
  const queryString = urlParams.toString();
  const currentSearchHref = queryString ? `/search?${queryString}` : '/search';
  const exportHref = `/api/export/search.csv${qs({ q: filters.q, company: filters.company })}`;

  return (
    <div className="grid">
      <Card>
        <CardHeader>
          <CardTitle>搜索</CardTitle>
          <CardDescription>统一 filters 契约：q/track/company/status/change_type/date_range/risk/sort/view。</CardDescription>
        </CardHeader>
        <CardContent>
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center', marginBottom: 10 }}>
            <SearchExportActions canExport={canExport} exportHref={exportHref} />
          </div>
          <FilterChips />
          <div style={{ marginTop: 10 }}>
            <SearchFiltersPanel initial={filters} />
          </div>
        </CardContent>
      </Card>

      <Suspense key={queryString || 'search-default'} fallback={<SearchResultsFallback />}>
        <SearchResultsSection
          filters={filters}
          page={page}
          pageSize={pageSize}
          isPro={isPro}
          currentSearchHref={currentSearchHref}
        />
      </Suspense>
    </div>
  );
}
