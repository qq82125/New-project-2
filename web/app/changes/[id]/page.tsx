import Link from 'next/link';
import { headers } from 'next/headers';
import { redirect } from 'next/navigation';

import { apiBase } from '../../../lib/api-server';
import { apiGet } from '../../../lib/api';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../../components/ui/card';
import { Badge } from '../../../components/ui/badge';
import { EmptyState, ErrorState } from '../../../components/States';
import { CHANGE_TYPE_ZH, IVD_CATEGORY_ZH, STATUS_ZH, labelFrom } from '../../../constants/display';

type ChangeDetailData = {
  id: number;
  change_type: string;
  change_date?: string | null;
  changed_at?: string | null;
  entity_type: string;
  entity_id: string;
  changed_fields: Record<string, { old?: unknown; new?: unknown }>;
  before_json?: Record<string, unknown> | null;
  after_json?: Record<string, unknown> | null;
};

type ProductData = {
  id: string;
  name: string;
  reg_no?: string | null;
  udi_di?: string | null;
  status: string;
  approved_date?: string | null;
  expiry_date?: string | null;
  class_name?: string | null;
  ivd_category?: string | null;
  company?: { id: string; name: string; country?: string | null } | null;
};

export default async function ChangeDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const API_BASE = apiBase();
  const cookie = (await headers()).get('cookie') || '';
  const authRes = await fetch(`${API_BASE}/api/auth/me`, {
    method: 'GET',
    headers: cookie ? { cookie } : undefined,
    cache: 'no-store',
  });
  if (authRes.status === 401) redirect('/login');

  const { id } = await params;
  const res = await apiGet<ChangeDetailData>(`/api/changes/${id}`);

  if (res.error) return <ErrorState text={`变化详情加载失败：${res.error}`} />;
  if (!res.data) return <EmptyState text="未找到该变化记录" />;

  const item = res.data;
  const productId = item.entity_type === 'product' ? String(item.entity_id) : '';
  const productRes = productId ? await apiGet<ProductData>(`/api/products/${productId}`) : { data: null, error: null };
  const product = productRes.data;

  return (
    <div className="grid">
      <Card>
        <CardHeader>
          <CardTitle>{product?.name || `产品变化记录 #${item.id}`}</CardTitle>
          <CardDescription>
            当前实况 · 最近变化：{labelFrom(CHANGE_TYPE_ZH, item.change_type)} ·{' '}
            {item.change_date ? new Date(item.change_date).toLocaleString() : item.changed_at ? new Date(item.changed_at).toLocaleString() : '-'}
          </CardDescription>
        </CardHeader>
        <CardContent style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
          {product ? (
            <>
              <Badge variant="muted">注册证号: {product.reg_no || '-'}</Badge>
              <Badge variant="muted">UDI-DI: {product.udi_di || '-'}</Badge>
              <Badge variant="success">IVD分类: {labelFrom(IVD_CATEGORY_ZH, product.ivd_category)}</Badge>
              <Badge variant="muted">状态: {labelFrom(STATUS_ZH, product.status)}</Badge>
              <Badge variant="muted">批准日期: {product.approved_date || '-'}</Badge>
              <Badge variant="muted">失效日期: {product.expiry_date || '-'}</Badge>
            </>
          ) : (
            <>
              <Badge variant="muted">实体类型: {item.entity_type || '-'}</Badge>
              <Badge variant="muted">实体ID: {item.entity_id || '-'}</Badge>
            </>
          )}
          {product?.company ? (
            <Link className="muted" href={`/companies/${product.company.id}`}>
              企业：{product.company.name}
            </Link>
          ) : null}
          {product ? (
            <Link className="muted" href={`/products/${product.id}`}>
              打开产品详情
            </Link>
          ) : null}
          <Link className="muted" href="/changes/export">
            返回历史变化导出
          </Link>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>本次变化摘要</CardTitle>
          <CardDescription>仅作审计参考，不影响上方“当前实况”。</CardDescription>
        </CardHeader>
        <CardContent>
          <details>
            <summary className="muted" style={{ cursor: 'pointer' }}>
              展开审计数据（字段差异与原始快照）
            </summary>
            <pre style={{ marginTop: 10, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
              {JSON.stringify(
                {
                  changed_fields: item.changed_fields || {},
                  before_json: item.before_json || null,
                  after_json: item.after_json || null,
                },
                null,
                2
              )}
            </pre>
          </details>
        </CardContent>
      </Card>
    </div>
  );
}
