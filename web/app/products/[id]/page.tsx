import { headers } from 'next/headers';
import { redirect } from 'next/navigation';
import Link from 'next/link';
import { EmptyState, ErrorState } from '../../../components/States';
import { apiGet } from '../../../lib/api';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../../components/ui/card';
import { Badge } from '../../../components/ui/badge';
import { formatUdiDiDisplay, labelField, labelStatus } from '../../../lib/labelMap';

const API_BASE = process.env.API_BASE_URL || process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

type ProductData = {
  id: string;
  name: string;
  reg_no?: string | null;
  udi_di: string;
  status: string;
  approved_date?: string | null;
  expiry_date?: string | null;
  class_name?: string | null;
  company?: { id: string; name: string; country?: string | null } | null;
};

export default async function ProductDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const cookie = (await headers()).get('cookie') || '';
  const meRes = await fetch(`${API_BASE}/api/auth/me`, {
    method: 'GET',
    headers: cookie ? { cookie } : undefined,
    cache: 'no-store',
  });
  if (meRes.status === 401) redirect('/login');

  const { id } = await params;
  const res = await apiGet<ProductData>(`/api/products/${id}`);

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
            <Badge variant="muted">
              {labelField('reg_no')}：{res.data.reg_no || '-'}
            </Badge>
            <Badge variant="muted">
              {labelField('udi_di')}：{formatUdiDiDisplay(res.data.udi_di)}
            </Badge>
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
              {labelField('status')}：{labelStatus(res.data.status)}
            </Badge>
          </div>
          <div className="columns-2">
            <div>
              <div className="muted">{labelField('approved_date')}</div>
              <div>{res.data.approved_date || '-'}</div>
            </div>
            <div>
              <div className="muted">{labelField('expiry_date')}</div>
              <div>{res.data.expiry_date || '-'}</div>
            </div>
          </div>
          <div>
            <div className="muted">{labelField('class_name', '类别')}</div>
            <div>{res.data.class_name || '-'}</div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent>
          <Link href={`/search?reg_no=${encodeURIComponent(res.data.reg_no || '')}`}>按注册证号搜索</Link>
        </CardContent>
      </Card>
    </div>
  );
}
