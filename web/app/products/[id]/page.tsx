import { headers } from 'next/headers';
import { redirect } from 'next/navigation';
import Link from 'next/link';
import { EmptyState, ErrorState } from '../../../components/States';
import { apiGet } from '../../../lib/api';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../../components/ui/card';
import { Badge } from '../../../components/ui/badge';

import { apiBase } from '../../../lib/api-server';
import { getMe } from '../../../lib/getMe';
import ProUpgradeHint from '../../../components/plan/ProUpgradeHint';
import { PRO_COPY, PRO_TRIAL_HREF } from '../../../constants/pro';
import { IVD_CATEGORY_ZH, STATUS_ZH, labelFrom } from '../../../constants/display';

type ProductData = {
  id: string;
  name: string;
  reg_no?: string | null;
  udi_di: string;
  status: string;
  approved_date?: string | null;
  expiry_date?: string | null;
  class_name?: string | null;
  ivd_category?: string | null;
  company?: { id: string; name: string; country?: string | null } | null;
};

type ProductParamItem = {
  id: string;
  param_code: string;
  value_num?: number | null;
  value_text?: string | null;
  unit?: string | null;
  confidence: number;
  evidence_text: string;
  evidence_page?: number | null;
  source?: string | null;
};

type ProductParamsData = {
  product_id: string;
  product_name: string;
  items: ProductParamItem[];
};

export default async function ProductDetailPage({ params }: { params: Promise<{ id: string }> }) {
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
  const res = await apiGet<ProductData>(`/api/products/${id}`);
  const paramsRes = isPro ? await apiGet<ProductParamsData>(`/api/products/${id}/params`) : { data: null, error: null };

  if (res.error) {
    return <ErrorState text={`产品加载失败：${res.error}`} />;
  }
  if (!res.data) {
    return <EmptyState text="产品不存在" />;
  }

  return (
    <div className="grid">
      <Card>
        <CardHeader>
          <CardTitle>{res.data.name}</CardTitle>
          <CardDescription>
            {res.data.company ? (
              <>
                <span className="muted">企业：</span>
                <Link href={`/companies/${res.data.company.id}`}>{res.data.company.name}</Link>
              </>
            ) : (
              <span className="muted">企业：-</span>
            )}
          </CardDescription>
        </CardHeader>
        <CardContent className="grid">
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
            <Badge variant="muted">注册证号: {res.data.reg_no || '-'}</Badge>
            <Badge variant="muted">UDI-DI: {res.data.udi_di}</Badge>
            <Badge variant="success">IVD类别: {labelFrom(IVD_CATEGORY_ZH, res.data.ivd_category)}</Badge>
            <Badge
              variant={
                res.data.status === 'active'
                  ? 'success'
                  : res.data.status === 'expired'
                    ? 'warning'
                    : res.data.status === 'cancelled'
                      ? 'danger'
                    : 'muted'
              }
            >
              状态: {labelFrom(STATUS_ZH, res.data.status)}
            </Badge>
          </div>
          <div className="columns-2">
            <div>
              <div className="muted">批准日期</div>
              <div>{res.data.approved_date || '-'}</div>
            </div>
            <div>
              <div className="muted">失效日期</div>
              <div>{res.data.expiry_date || '-'}</div>
            </div>
          </div>
          <div>
            <div className="muted">分类码</div>
            <div>{res.data.class_name || '-'}</div>
          </div>
        </CardContent>
      </Card>

      {!isPro ? (
        <ProUpgradeHint
          text={PRO_COPY.product_free_hint}
          ctaHref={PRO_TRIAL_HREF}
        />
      ) : null}

      {isPro ? (
        <Card>
          <CardHeader>
            <CardTitle>参数摘要</CardTitle>
            <CardDescription>来源于说明书/附件抽取，包含证据文本。</CardDescription>
          </CardHeader>
          <CardContent className="grid">
            {paramsRes.error ? (
              <ErrorState text={`参数加载失败：${paramsRes.error}`} />
            ) : !paramsRes.data || (paramsRes.data.items || []).length === 0 ? (
              <EmptyState text="暂无结构化参数" />
            ) : (
              (paramsRes.data.items || []).slice(0, 20).map((it) => (
                <div key={it.id} className="card">
                  <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
                    <Badge variant="muted">{it.param_code}</Badge>
                    <Badge variant="muted">置信度: {Number(it.confidence || 0).toFixed(2)}</Badge>
                    {it.source ? <Badge variant="muted">来源: {it.source}</Badge> : null}
                  </div>
                  <div style={{ marginTop: 8 }}>
                    值: {it.value_num ?? it.value_text ?? '-'} {it.unit || ''}
                  </div>
                  <div className="muted" style={{ marginTop: 6 }}>
                    证据{it.evidence_page != null ? ` (p.${it.evidence_page})` : ''}: {it.evidence_text}
                  </div>
                </div>
              ))
            )}
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <CardContent>
          <Link href={`/search?reg_no=${encodeURIComponent(res.data.reg_no || '')}`}>按注册证号搜索</Link>
        </CardContent>
      </Card>
    </div>
  );
}
