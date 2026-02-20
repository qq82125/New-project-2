import { headers } from 'next/headers';
import { redirect } from 'next/navigation';
import Link from 'next/link';
import { EmptyState, ErrorState } from '../../../components/States';
import { apiGet, qs } from '../../../lib/api';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../../components/ui/card';
import { apiBase } from '../../../lib/api-server';
import CopyButton from '../../../components/common/CopyButton';
import StatusBadge from '../../../components/common/StatusBadge';
import AddToBenchmarkButton from '../../../components/common/AddToBenchmarkButton';
import DetailTabs from '../../../components/detail/DetailTabs';
import FieldGroups from '../../../components/detail/FieldGroups';
import ChangesTimeline from '../../../components/detail/ChangesTimeline';
import EvidenceList from '../../../components/detail/EvidenceList';
import VariantsTable, { type VariantRow } from '../../../components/detail/VariantsTable';
import { buildProductOverviewGroups } from '../../../components/detail/field-dictionaries';
import { getRegistrationTimeline } from '../../../lib/api/registrations';
import { ApiHttpError } from '../../../lib/api/client';
import { toChangeRows, toEvidenceRows } from '../../../lib/detail';
import { buildSearchUrl } from '../../../lib/search-filters';
import SimilarItems from '../../../components/detail/SimilarItems';
import type { UnifiedTableRow } from '../../../components/table/columns';

type ProductData = {
  id: string;
  name: string;
  reg_no?: string | null;
  registrations?: Array<string | { registration_no?: string | null; reg_no?: string | null }> | null;
  udi_di?: string | null;
  status: string;
  approved_date?: string | null;
  expiry_date?: string | null;
  class_name?: string | null;
  model?: string | null;
  specification?: string | null;
  category?: string | null;
  description?: string | null;
  ivd_category?: string | null;
  company?: { id: string; name: string; country?: string | null } | null;
};

type SearchData = {
  items: Array<{
    product: {
      id: string;
      name: string;
      reg_no?: string | null;
      udi_di?: string | null;
      status?: string | null;
      expiry_date?: string | null;
      company?: { id: string; name: string } | null;
    };
  }>;
};

type VariantItem = {
  di: string;
  model_spec?: string | null;
  manufacturer?: string | null;
  packaging_json?: unknown[] | unknown | null;
};

type RegistrationData = {
  registration_no: string;
  variants: VariantItem[];
};

function firstRegistrationNo(product: ProductData): string | null {
  if (product.reg_no) return product.reg_no;
  const regs = product.registrations || [];
  for (const item of regs) {
    if (typeof item === 'string' && item) return item;
    if (item && typeof item === 'object') {
      if (item.registration_no) return item.registration_no;
      if (item.reg_no) return item.reg_no;
    }
  }
  return null;
}

function isNotFound(err: unknown): boolean {
  return err instanceof ApiHttpError && err.status === 404;
}

function formatError(err: unknown): string {
  if (err instanceof Error && err.message) return err.message;
  return '未知错误';
}

function packagingCount(v: unknown): number {
  if (!v) return 0;
  if (Array.isArray(v)) return v.length;
  if (typeof v === 'object' && Array.isArray((v as { packings?: unknown[] }).packings)) {
    return ((v as { packings?: unknown[] }).packings || []).length;
  }
  return 0;
}

function scoreSimilarItem(input: {
  company: string;
  keyword: string;
  productName: string;
  productCompany: string;
}): number {
  let score = 0;
  if (input.company && input.company === input.productCompany) score += 3;
  if (input.keyword && input.productName.includes(input.keyword)) score += 2;
  return score;
}

function toSimilarRows(
  items: SearchData['items'],
  currentId: string,
  currentRegNo: string,
  backHref: string,
  company: string,
  keyword: string,
): UnifiedTableRow[] {
  const unique = new Map<string, SearchData['items'][number]>();
  for (const item of items) {
    const key = item.product.reg_no || `product:${item.product.id}`;
    if (!key) continue;
    if (item.product.id === currentId) continue;
    if (currentRegNo && item.product.reg_no === currentRegNo) continue;
    if (!unique.has(key)) unique.set(key, item);
  }

  const sorted = Array.from(unique.values()).sort((a, b) => {
    const sa = scoreSimilarItem({
      company,
      keyword,
      productName: String(a.product.name || ''),
      productCompany: String(a.product.company?.name || ''),
    });
    const sb = scoreSimilarItem({
      company,
      keyword,
      productName: String(b.product.name || ''),
      productCompany: String(b.product.company?.name || ''),
    });
    return sb - sa;
  });

  const back = encodeURIComponent(backHref);
  return sorted.slice(0, 8).map((item) => {
    const regNo = String(item.product.reg_no || '').trim();
    const detailHref = regNo
      ? `/registrations/${encodeURIComponent(regNo)}?back=${back}`
      : `/products/${encodeURIComponent(item.product.id)}?back=${back}`;

    return {
      id: item.product.id,
      product_name: item.product.name || '-',
      company_name: item.product.company?.name || '-',
      registration_no: regNo || '-',
      status: item.product.status || '-',
      expiry_date: item.product.expiry_date || '-',
      udi_di: item.product.udi_di || '-',
      badges: [
        ...(company && item.product.company?.name === company ? [{ kind: 'custom' as const, value: 'same-company' }] : []),
      ],
      detail_href: detailHref,
      action: regNo
        ? {
            type: 'benchmark' as const,
            registration_no: regNo,
            set_id: 'my-benchmark',
          }
        : {
            label: 'N/A',
            disabled: true,
          },
    };
  });
}

export default async function ProductDetailPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams?: Promise<{ back?: string }>;
}) {
  const API_BASE = apiBase();
  const cookie = (await headers()).get('cookie') || '';
  const meRes = await fetch(`${API_BASE}/api/auth/me`, {
    method: 'GET',
    headers: cookie ? { cookie } : undefined,
    cache: 'no-store',
  });
  if (meRes.status === 401) redirect('/login');

  const [{ id }, sp] = await Promise.all([
    params,
    searchParams ?? Promise.resolve({ back: undefined as string | undefined }),
  ]);

  let backRaw = '';
  if (typeof sp.back === 'string') {
    try {
      backRaw = decodeURIComponent(sp.back);
    } catch {
      backRaw = '';
    }
  }

  const res = await apiGet<ProductData>(`/api/products/${id}`);
  if (res.error) {
    return <ErrorState text={`产品加载失败：${res.error}`} />;
  }
  if (!res.data) {
    return <EmptyState text="产品不存在" />;
  }

  const anchorRegNo = firstRegistrationNo(res.data);
  const safeBackHref = backRaw.startsWith('/search') || backRaw.startsWith('/benchmarks')
    ? backRaw
    : buildSearchUrl({ q: anchorRegNo || res.data.reg_no || res.data.name || '' });

  const regRes = anchorRegNo
    ? await apiGet<RegistrationData>(`/api/registrations/${encodeURIComponent(anchorRegNo)}`)
    : { data: null, error: null, status: null };

  const timelineResult = anchorRegNo
    ? await Promise.resolve(
        getRegistrationTimeline(anchorRegNo)
          .then((items) => ({ data: items, error: null as unknown }))
          .catch((error) => ({ data: [], error })),
      )
    : { data: [], error: null as unknown };

  const timelineNotFound = timelineResult.error ? isNotFound(timelineResult.error) : false;

  const evidenceRows = toEvidenceRows(timelineResult.data as any);
  const changeRows = toChangeRows(timelineResult.data as any);

  const variants = regRes.data?.variants || [];
  const variantRows: VariantRow[] = variants.map((item) => ({
    di: item.di,
    model_spec: item.model_spec || '',
    manufacturer: item.manufacturer || '',
    packaging: packagingCount(item.packaging_json) ? `${packagingCount(item.packaging_json)} 层` : '-',
  }));

  const keyword = String(res.data.ivd_category || res.data.class_name || res.data.category || '').trim();
  const company = String(res.data.company?.name || '').trim();
  const [companyRes, keywordRes] = await Promise.all([
    company
      ? apiGet<SearchData>(
          `/api/search${qs({ company, page: 1, page_size: 20, sort_by: 'approved_date', sort_order: 'desc' })}`,
        )
      : Promise.resolve({ data: { items: [] }, error: null }),
    keyword
      ? apiGet<SearchData>(
          `/api/search${qs({ q: keyword, page: 1, page_size: 20, sort_by: 'approved_date', sort_order: 'desc' })}`,
        )
      : Promise.resolve({ data: { items: [] }, error: null }),
  ]);
  const similarRows = toSimilarRows(
    [...(companyRes.data?.items || []), ...(keywordRes.data?.items || [])],
    res.data.id,
    anchorRegNo || '',
    safeBackHref,
    company,
    keyword,
  );

  return (
    <div className="grid">
      <Card>
        <CardHeader>
          <CardTitle>证据资产页</CardTitle>
          <CardDescription>
            <Link href={safeBackHref}>返回搜索结果</Link>
          </CardDescription>
        </CardHeader>
        <CardContent className="grid">
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
            <span className="muted">注册证号：</span>
            <strong>{anchorRegNo || '-'}</strong>
            {anchorRegNo ? <CopyButton text={anchorRegNo} label="复制" size="sm" /> : null}
            {anchorRegNo ? <AddToBenchmarkButton registrationNo={anchorRegNo} setId="my-benchmark" /> : null}
            <span className="muted" style={{ marginLeft: 8 }}>状态：</span>
            <StatusBadge status={res.data.status} />
          </div>

          <DetailTabs
            items={[
              {
                key: 'overview',
                label: 'Overview',
                content: (
                  <FieldGroups
                    groups={buildProductOverviewGroups(
                      res.data,
                      anchorRegNo || '',
                      variants.map((v) => v.di).filter(Boolean),
                    )}
                  />
                ),
              },
              {
                key: 'changes',
                label: 'Changes',
                content:
                  timelineResult.error && !timelineNotFound ? (
                    <ErrorState text={`变更加载失败（${formatError(timelineResult.error)}）`} />
                  ) : anchorRegNo ? (
                    <ChangesTimeline changes={changeRows} />
                  ) : (
                    <EmptyState text="暂无变更记录（该产品未绑定注册证）" />
                  ),
              },
              {
                key: 'evidence',
                label: 'Evidence',
                content:
                  timelineResult.error && !timelineNotFound ? (
                    <ErrorState text={`证据加载失败（${formatError(timelineResult.error)}）`} />
                  ) : anchorRegNo ? (
                    <EvidenceList evidences={evidenceRows} />
                  ) : (
                    <EmptyState text="暂无证据（该产品未绑定注册证）" />
                  ),
              },
              {
                key: 'variants',
                label: 'Variants(DI)',
                content: regRes.error ? (
                  <ErrorState text={`DI 加载失败：${regRes.error}`} />
                ) : (
                  <VariantsTable rows={variantRows} />
                ),
              },
            ]}
          />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>同类推荐</CardTitle>
          <CardDescription>规则：同公司优先，其次同类别关键词</CardDescription>
        </CardHeader>
        <CardContent>
          <SimilarItems rows={similarRows} />
        </CardContent>
      </Card>

      {anchorRegNo ? (
        <Card>
          <CardContent>
            <Link href={`/registrations/${encodeURIComponent(anchorRegNo)}?back=${encodeURIComponent(safeBackHref)}`}>
              打开注册证详情
            </Link>
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}
