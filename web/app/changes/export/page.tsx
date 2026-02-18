import Link from 'next/link';
import { headers } from 'next/headers';
import { redirect } from 'next/navigation';

import { Badge } from '../../../components/ui/badge';
import { Button } from '../../../components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../../components/ui/card';
import { Input } from '../../../components/ui/input';
import { Select } from '../../../components/ui/select';
import { EmptyState, ErrorState } from '../../../components/States';
import PaginationControls from '../../../components/PaginationControls';
import { apiGet, qs } from '../../../lib/api';
import { apiBase } from '../../../lib/api-server';
import { CHANGE_TYPE_ZH, IVD_CATEGORY_ZH, labelFrom } from '../../../constants/display';

type PageParams = {
  days?: string;
  change_type?: string;
  q?: string;
  company?: string;
  reg_no?: string;
  page?: string;
  page_size?: string;
};

type ChangesListData = {
  days: number;
  total: number;
  page: number;
  page_size: number;
  items: Array<{
    id: number;
    change_type: string;
    change_date?: string | null;
    changed_at?: string | null;
    product: {
      id: string;
      name: string;
      reg_no?: string | null;
      udi_di?: string | null;
      ivd_category?: string | null;
      company?: { id: string; name: string } | null;
    };
  }>;
};

export default async function ChangesExportPage({ searchParams }: { searchParams: Promise<PageParams> }) {
  const API_BASE = apiBase();
  const cookie = (await headers()).get('cookie') || '';
  const authRes = await fetch(`${API_BASE}/api/auth/me`, {
    method: 'GET',
    headers: cookie ? { cookie } : undefined,
    cache: 'no-store',
  });
  if (authRes.status === 401) redirect('/login');

  const params = await searchParams;
  const days = Number(params.days || '30');
  const page = Number(params.page || '1');
  const pageSize = Number(params.page_size || '30');

  const query = qs({
    days,
    change_type: params.change_type,
    q: params.q,
    company: params.company,
    reg_no: params.reg_no,
    page,
    page_size: pageSize,
  });
  const exportHref = `/api/export/changes.csv${qs({
    days,
    change_type: params.change_type,
    q: params.q,
    company: params.company,
    reg_no: params.reg_no,
  })}`;
  const res = await apiGet<ChangesListData>(`/api/changes${query}`);

  return (
    <div className="grid">
      <Card>
        <CardHeader>
          <CardTitle>历史变化导出</CardTitle>
          <CardDescription>按时间与筛选条件导出变化记录（仅 IVD）。</CardDescription>
        </CardHeader>
        <CardContent>
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center', marginBottom: 10 }}>
            <a className="ui-btn" href={exportHref}>
              导出变化 CSV
            </a>
            <Badge variant="success">专业版</Badge>
          </div>
          <div className="muted" style={{ marginBottom: 12 }}>
            导出字段：变化ID、变化类型、变化时间、产品ID、产品名称、注册证号、UDI-DI、IVD分类、企业名称。
          </div>
          <form className="controls" method="GET">
            <Select name="days" defaultValue={String(days)}>
              <option value="7">近 7 天</option>
              <option value="30">近 30 天</option>
              <option value="90">近 90 天</option>
              <option value="180">近 180 天</option>
              <option value="365">近 365 天</option>
            </Select>
            <Select name="change_type" defaultValue={params.change_type || ''}>
              <option value="">全部变化类型</option>
              <option value="new">新增</option>
              <option value="update">变更</option>
              <option value="expire">失效</option>
              <option value="cancel">注销</option>
            </Select>
            <Input name="q" defaultValue={params.q} placeholder="产品名称关键词" />
            <Input name="company" defaultValue={params.company} placeholder="企业名称" />
            <Input name="reg_no" defaultValue={params.reg_no} placeholder="注册证号" />
            <Input name="page_size" defaultValue={String(pageSize)} placeholder="每页数量" inputMode="numeric" />
            <Button type="submit">查询</Button>
          </form>
        </CardContent>
      </Card>

      {res.error ? (
        <ErrorState text={`加载失败：${res.error}`} />
      ) : !res.data ? (
        <EmptyState text="暂无变化记录" />
      ) : (
        <>
          <Card>
            <CardContent style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
              <Badge variant="muted">共 {res.data.total} 条</Badge>
              <span className="muted">
                第 {res.data.page} / {Math.max(1, Math.ceil(res.data.total / Math.max(1, res.data.page_size)))} 页（每页 {res.data.page_size} 条）
              </span>
            </CardContent>
          </Card>

          {res.data.items.length === 0 ? (
            <EmptyState text="暂无匹配结果" />
          ) : (
            <div className="list">
              {res.data.items.map((item) => (
                <Card key={item.id}>
                  <CardHeader>
                    <CardTitle>
                      <Link href={`/products/${item.product.id}`}>{item.product.name}</Link>
                    </CardTitle>
                    <CardDescription>
                      {labelFrom(CHANGE_TYPE_ZH, item.change_type)} ·{' '}
                      {item.change_date
                        ? new Date(item.change_date).toLocaleString()
                        : item.changed_at
                          ? new Date(item.changed_at).toLocaleString()
                          : '-'}
                    </CardDescription>
                  </CardHeader>
                  <CardContent style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
                    <Badge variant="muted">注册证号: {item.product.reg_no || '-'}</Badge>
                    <Badge variant="muted">UDI-DI: {item.product.udi_di || '-'}</Badge>
                    <Badge variant="muted">IVD分类: {labelFrom(IVD_CATEGORY_ZH, item.product.ivd_category)}</Badge>
                    <Badge variant="muted">企业: {item.product.company?.name || '-'}</Badge>
                    <Link className="muted" href={`/changes/${item.id}`}>
                      查看详情
                    </Link>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}

          <Card>
            <CardContent style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
              <PaginationControls
                basePath="/changes/export"
                params={{
                  days: String(days),
                  change_type: params.change_type,
                  q: params.q,
                  company: params.company,
                  reg_no: params.reg_no,
                }}
                page={res.data.page}
                pageSize={res.data.page_size}
                total={res.data.total}
              />
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
