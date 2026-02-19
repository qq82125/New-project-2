import Link from 'next/link';
import { EmptyState, ErrorState } from '../../../components/States';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../../components/ui/card';
import CopyButton from '../../../components/common/CopyButton';
import StatusBadge from '../../../components/common/StatusBadge';
import AddToBenchmarkButton from '../../../components/common/AddToBenchmarkButton';
import { getRegistration, getRegistrationTimeline } from '../../../lib/api/registrations';
import type { TimelineEvent } from '../../../lib/api/types';
import { ApiHttpError } from '../../../lib/api/client';
import { toChangeRows, toEvidenceRows } from '../../../lib/detail';
import { buildSearchUrl } from '../../../lib/search-filters';
import DetailTabs from '../../../components/detail/DetailTabs';
import FieldGroups from '../../../components/detail/FieldGroups';
import ChangesTimeline from '../../../components/detail/ChangesTimeline';
import EvidenceList from '../../../components/detail/EvidenceList';
import VariantsTable, { type VariantRow } from '../../../components/detail/VariantsTable';
import { buildRegistrationOverviewGroups } from '../../../components/detail/field-dictionaries';
import SimilarItems from '../../../components/detail/SimilarItems';
import { apiGet, qs } from '../../../lib/api';
import type { UnifiedTableRow } from '../../../components/table/columns';

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
  track: string;
  targetStatus: string;
  productName: string;
  productCompany: string;
  productStatus: string;
}): number {
  let score = 0;
  if (input.company && input.company === input.productCompany) score += 3;
  if (input.track && input.productName.includes(input.track)) score += 2;
  if (input.targetStatus && input.targetStatus === input.productStatus) score += 1;
  return score;
}

function toSimilarRows(
  items: SearchData['items'],
  currentRegNo: string,
  backHref: string,
  company: string,
  track: string,
  status: string,
): UnifiedTableRow[] {
  const byRegNo = new Map<string, SearchData['items'][number]>();
  for (const item of items) {
    const regNo = String(item.product.reg_no || '').trim();
    if (!regNo || regNo === currentRegNo) continue;
    if (!byRegNo.has(regNo)) byRegNo.set(regNo, item);
  }

  const sorted = Array.from(byRegNo.values()).sort((a, b) => {
    const sa = scoreSimilarItem({
      company,
      track,
      targetStatus: status,
      productName: String(a.product.name || ''),
      productCompany: String(a.product.company?.name || ''),
      productStatus: String(a.product.status || ''),
    });
    const sb = scoreSimilarItem({
      company,
      track,
      targetStatus: status,
      productName: String(b.product.name || ''),
      productCompany: String(b.product.company?.name || ''),
      productStatus: String(b.product.status || ''),
    });
    return sb - sa;
  });

  const back = encodeURIComponent(backHref);
  return sorted.slice(0, 8).map((item) => {
    const regNo = String(item.product.reg_no || '').trim();
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
        ...(track && item.product.name?.includes(track) ? [{ kind: 'custom' as const, value: 'same-track' }] : []),
      ],
      detail_href: `/registrations/${encodeURIComponent(regNo)}?back=${back}`,
      action: {
        type: 'benchmark' as const,
        registration_no: regNo,
        set_id: 'my-benchmark',
      },
    };
  });
}

export default async function RegistrationDetailPage({
  params,
  searchParams,
}: {
  params: Promise<{ registration_no: string }>;
  searchParams?: Promise<{ back?: string }>;
}) {
  const [{ registration_no }, sp] = await Promise.all([
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
  const safeBackHref = backRaw.startsWith('/search') || backRaw.startsWith('/benchmarks')
    ? backRaw
    : buildSearchUrl({ q: registration_no });

  const [registrationResult, timelineResult] = await Promise.allSettled([
    getRegistration(registration_no),
    getRegistrationTimeline(registration_no),
  ]);

  const registrationNotFound = registrationResult.status === 'rejected' && isNotFound(registrationResult.reason);
  const timelineNotFound = timelineResult.status === 'rejected' && isNotFound(timelineResult.reason);

  const registration = registrationResult.status === 'fulfilled' ? registrationResult.value : null;
  const timeline = timelineResult.status === 'fulfilled' ? timelineResult.value : [];

  const variants = registration?.variants || [];
  const evidenceRows = toEvidenceRows(timeline as TimelineEvent[]);
  const changeRows = toChangeRows(timeline as TimelineEvent[]);
  const variantRows: VariantRow[] = variants.map((item) => ({
    di: item.di,
    model_spec: item.model_spec || '',
    manufacturer: item.manufacturer || '',
    packaging: packagingCount(item.packaging_json) ? `${packagingCount(item.packaging_json)} 层` : '-',
  }));

  let similarRows: UnifiedTableRow[] = [];
  if (registration) {
    const company = String(registration.company || '').trim();
    const track = String(registration.track || '').trim();
    const status = String(registration.status || '').trim();
    const [companyRes, trackRes] = await Promise.all([
      company
        ? apiGet<SearchData>(
            `/api/search${qs({ company, page: 1, page_size: 20, sort_by: 'approved_date', sort_order: 'desc' })}`,
          )
        : Promise.resolve({ data: { items: [] }, error: null }),
      track
        ? apiGet<SearchData>(
            `/api/search${qs({ q: track, page: 1, page_size: 20, sort_by: 'approved_date', sort_order: 'desc' })}`,
          )
        : Promise.resolve({ data: { items: [] }, error: null }),
    ]);
    const merged = [...(companyRes.data?.items || []), ...(trackRes.data?.items || [])];
    similarRows = toSimilarRows(merged, registration.registration_no, safeBackHref, company, track, status);
  }

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
          {registrationResult.status === 'rejected' && !registrationNotFound ? (
            <ErrorState text={`加载失败，请重试（${formatError(registrationResult.reason)}）`} />
          ) : null}
          {!registration ? (
            <EmptyState text="暂无数据" />
          ) : (
            <>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                <span className="muted">注册证号：</span>
                <strong>{registration.registration_no}</strong>
                <CopyButton text={registration.registration_no} label="复制" size="sm" />
                <AddToBenchmarkButton registrationNo={registration.registration_no} setId="my-benchmark" />
                <span className="muted" style={{ marginLeft: 8 }}>状态：</span>
                <StatusBadge status={registration.status} />
              </div>

              <DetailTabs
                items={[
                  {
                    key: 'overview',
                    label: 'Overview',
                    content: <FieldGroups groups={buildRegistrationOverviewGroups(registration, variants)} />,
                  },
                  {
                    key: 'changes',
                    label: 'Changes',
                    content:
                      timelineResult.status === 'rejected' && !timelineNotFound ? (
                        <ErrorState text={`变更加载失败（${formatError(timelineResult.reason)}）`} />
                      ) : (
                        <ChangesTimeline changes={changeRows} />
                      ),
                  },
                  {
                    key: 'evidence',
                    label: 'Evidence',
                    content:
                      timelineResult.status === 'rejected' && !timelineNotFound ? (
                        <ErrorState text={`证据加载失败（${formatError(timelineResult.reason)}）`} />
                      ) : (
                        <EvidenceList evidences={evidenceRows} />
                      ),
                  },
                  {
                    key: 'variants',
                    label: 'Variants(DI)',
                    content: <VariantsTable rows={variantRows} />,
                  },
                ]}
              />
            </>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>同类推荐</CardTitle>
          <CardDescription>规则：同公司优先，其次同赛道关键词</CardDescription>
        </CardHeader>
        <CardContent>
          <SimilarItems rows={similarRows} />
        </CardContent>
      </Card>
    </div>
  );
}
