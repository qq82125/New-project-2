import { headers } from 'next/headers';
import { redirect } from 'next/navigation';
import Link from 'next/link';
import { EmptyState, ErrorState } from '../../../components/States';
import { apiGet } from '../../../lib/api';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../../components/ui/card';
import { Badge } from '../../../components/ui/badge';

import { apiBase } from '../../../lib/api-server';

type CompanyData = {
  id: string;
  name: string;
  country?: string | null;
};

export default async function CompanyDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const API_BASE = apiBase();
  const cookie = (await headers()).get('cookie') || '';
  const meRes = await fetch(`${API_BASE}/api/auth/me`, {
    method: 'GET',
    headers: cookie ? { cookie } : undefined,
    cache: 'no-store',
  });
  if (meRes.status === 401) redirect('/login');

  const { id } = await params;
  const res = await apiGet<CompanyData>(`/api/companies/${id}`);

  if (res.error) {
    return <ErrorState text={`企业加载失败：${res.error}`} />;
  }
  if (!res.data) {
    return <EmptyState text="企业不存在" />;
  }

  return (
    <div className="grid">
      <Card>
        <CardHeader>
          <CardTitle>{res.data.name}</CardTitle>
          <CardDescription>企业详情</CardDescription>
        </CardHeader>
        <CardContent className="grid">
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
            <Badge variant="muted">country: {res.data.country || '-'}</Badge>
            <Badge variant="muted">id: {res.data.id}</Badge>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent>
          <Link href={`/search?company=${encodeURIComponent(res.data.name)}`}>查看该企业相关产品</Link>
        </CardContent>
      </Card>
    </div>
  );
}
