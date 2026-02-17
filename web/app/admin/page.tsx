import Link from 'next/link';
import { headers } from 'next/headers';
import { notFound, redirect } from 'next/navigation';

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';

import { apiBase } from '../../lib/api-server';
import { apiGet } from '../../lib/api';

type AdminMe = { id: number; email: string; role: string };
type AdminMeResp = { code: number; message: string; data: AdminMe };

type AdminStats = {
  total_ivd_products: number;
  rejected_total: number;
  by_ivd_category: Array<{ key: string; value: number }>;
  by_source: Array<{ key: string; value: number }>;
};

export const dynamic = 'force-dynamic';

async function getAdminMe(): Promise<AdminMe> {
  const API_BASE = apiBase();
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
  const statsRes = await apiGet<AdminStats>('/api/admin/stats?limit=20');

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
          <Link className="ui-btn" href="/admin/data-sources">
            数据源管理
          </Link>
          <Link className="ui-btn" href="/admin/contact">
            联系信息
          </Link>
          <Link className="ui-btn" href="/admin/users">
            用户与会员
          </Link>
          <Link className="ui-btn" href="/admin/udi-links">
            UDI待映射
          </Link>
          <Link className="ui-btn" href="/admin/pending">
            Pending队列
          </Link>
          <Link className="ui-btn" href="/admin/conflicts">
            冲突队列
          </Link>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>数据概览（IVD口径）</CardTitle>
          <CardDescription>基于 products.is_ivd=true 的当前库存快照。</CardDescription>
        </CardHeader>
        <CardContent className="grid">
          {statsRes.error ? (
            <div className="muted">加载失败：{statsRes.error}</div>
          ) : !statsRes.data ? (
            <div className="muted">暂无数据</div>
          ) : (
            <>
              <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
                <Badge variant="muted">IVD 总数: {statsRes.data.total_ivd_products}</Badge>
                <Badge variant="muted">拒收记录: {statsRes.data.rejected_total}</Badge>
              </div>
              <div className="columns-2" style={{ gap: 12 }}>
                <div>
                  <div className="muted" style={{ marginBottom: 6 }}>
                    IVD 分类分布
                  </div>
                  <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                    {(statsRes.data.by_ivd_category || []).slice(0, 8).map((x) => (
                      <Badge key={x.key} variant="muted">
                        {x.key}: {x.value}
                      </Badge>
                    ))}
                  </div>
                </div>
                <div>
                  <div className="muted" style={{ marginBottom: 6 }}>
                    来源分布
                  </div>
                  <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                    {(statsRes.data.by_source || []).slice(0, 8).map((x) => (
                      <Badge key={x.key} variant="muted">
                        {x.key}: {x.value}
                      </Badge>
                    ))}
                  </div>
                </div>
              </div>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
