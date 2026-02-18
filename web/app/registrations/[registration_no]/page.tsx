import Link from 'next/link';
import { apiGet } from '../../../lib/api';
import { EmptyState, ErrorState } from '../../../components/States';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../../components/ui/card';
import { Badge } from '../../../components/ui/badge';
import { STATUS_ZH, labelFrom } from '../../../constants/display';
import PackagingTree, { type PackingEdge } from '../../../components/udi/PackagingTree';

type VariantItem = {
  di: string;
  model_spec?: string | null;
  manufacturer?: string | null;
  packaging_json?: any[] | any | null;
  evidence_raw_document_id?: string | null;
};

type RegistrationData = {
  id: string;
  registration_no: string;
  filing_no?: string | null;
  approval_date?: string | null;
  expiry_date?: string | null;
  status?: string | null;
  is_stub?: boolean | null;
  source_hint?: string | null;
  verified_by_nmpa?: boolean | null;
  variants: VariantItem[];
};

function packingsFromPackagingJson(v: any): any[] {
  if (!v) return [];
  if (Array.isArray(v)) return v;
  if (typeof v === 'object' && Array.isArray((v as any).packings)) return (v as any).packings;
  return [];
}

export default async function RegistrationDetailPage({ params }: { params: Promise<{ registration_no: string }> }) {
  const { registration_no } = await params;
  const res = await apiGet<RegistrationData>(`/api/registrations/${encodeURIComponent(registration_no)}`);

  if (res.error) return <ErrorState text={`注册证加载失败：${res.error}`} />;
  if (!res.data) return <EmptyState text="注册证不存在" />;

  const reg = res.data;
  const variants = reg.variants || [];

  return (
    <div className="grid">
      <Card>
        <CardHeader>
          <CardTitle>注册证详情</CardTitle>
          <CardDescription>以 registration_no 为唯一锚点，汇总规格（UDI-DI）与包装层级。</CardDescription>
        </CardHeader>
        <CardContent className="grid">
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
            <Badge variant="muted">注册证号: {reg.registration_no}</Badge>
              <Badge variant="muted">备案号: {reg.filing_no || '-'}</Badge>
              <Badge variant="muted">批准日期: {reg.approval_date || '-'}</Badge>
              <Badge variant="muted">有效期至: {reg.expiry_date || '-'}</Badge>
              <Badge variant="muted">状态: {labelFrom(STATUS_ZH, reg.status || '')}</Badge>
              {reg.is_stub && reg.source_hint === 'UDI' && reg.verified_by_nmpa === false ? (
                <Badge variant="warning">UDI来源｜待核验</Badge>
              ) : null}
            </div>
            <div>
              <Link href={`/search?reg_no=${encodeURIComponent(reg.registration_no)}`}>按该注册证号搜索产品</Link>
            </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>UDI 规格（DI）</CardTitle>
          <CardDescription>一个注册证可对应多个 DI；包装层级来自 UDI packingList（可用于按包装维度对齐报价/集采目录）。</CardDescription>
        </CardHeader>
        <CardContent className="grid">
          {variants.length === 0 ? (
            <EmptyState text="暂无 DI 规格记录（可先运行 udi:variants 生成绑定）" />
          ) : (
            variants.slice(0, 200).map((it) => {
              const packings = packingsFromPackagingJson(it.packaging_json) as PackingEdge[];
              return (
                <div key={it.di} className="card">
                  <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
                    <Badge variant="muted">DI: {it.di}</Badge>
                    {it.model_spec ? <Badge variant="muted">型号/货号: {it.model_spec}</Badge> : null}
                    {it.manufacturer ? <Badge variant="muted">注册人: {it.manufacturer}</Badge> : null}
                    {it.evidence_raw_document_id ? (
                      <Badge variant="muted">证据: {String(it.evidence_raw_document_id).slice(0, 8)}…</Badge>
                    ) : null}
                  </div>
                  {packings.length === 0 ? (
                    <div style={{ marginTop: 8 }}>
                      <PackagingTree packings={[]} />
                    </div>
                  ) : (
                    <div style={{ marginTop: 10 }} className="grid">
                      <div className="muted">包装层级</div>
                      <PackagingTree packings={packings} />
                    </div>
                  )}
                </div>
              );
            })
          )}
        </CardContent>
      </Card>
    </div>
  );
}
