import Link from 'next/link';
import { headers } from 'next/headers';
import { notFound, redirect } from 'next/navigation';

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';

const API_BASE = process.env.API_BASE_URL || process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

type AdminMe = { id: number; email: string; role: string };
type AdminMeResp = { code: number; message: string; data: AdminMe };

export const dynamic = 'force-dynamic';

async function getAdminMe(): Promise<AdminMe> {
  const cookie = (await headers()).get('cookie') || '';
  const res = await fetch(`${API_BASE}/api/admin/me`, {
    method: 'GET',
    headers: cookie ? { cookie } : undefined,
    cache: 'no-store',
  });

  if (res.status === 401) redirect('/login');
  if (res.status === 403) notFound();
  if (!res.ok) throw new Error(`admin/me failed: ${res.status}`);

  const body = (await res.json()) as AdminMeResp;
  if (body.code !== 0) throw new Error(body.message || 'admin/me returned error');
  return body.data;
}

export default async function AdminHomePage() {
  const me = await getAdminMe();

  return (
    <div className="grid">
      <Card>
        <CardHeader>
          <CardTitle>管理后台</CardTitle>
          <CardDescription>仅 admin 可访问。请先在 /login 使用管理员邮箱密码登录。</CardDescription>
        </CardHeader>
        <CardContent style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
          <span className="muted">当前：</span>
          <Badge variant="muted">#{me.id}</Badge>
          <Badge variant="muted">{me.email}</Badge>
          <Badge variant={me.role === 'admin' ? 'success' : 'muted'}>{me.role}</Badge>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>功能入口</CardTitle>
          <CardDescription>用户与会员管理走 cookie 登录态，不需要额外的 BasicAuth 账号密码。</CardDescription>
        </CardHeader>
        <CardContent style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
          <Link className="ui-btn" href="/admin/users">
            用户与会员
          </Link>
        </CardContent>
      </Card>
    </div>
  );
}

