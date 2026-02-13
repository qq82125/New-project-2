import Link from 'next/link';
import { headers } from 'next/headers';
import { redirect } from 'next/navigation';

import { Badge } from '../../components/ui/badge';
import { Button } from '../../components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card';
import { Input } from '../../components/ui/input';
import { Select } from '../../components/ui/select';
import { EmptyState, ErrorState } from '../../components/States';
import { apiGet, qs } from '../../lib/api';
import { apiBase } from '../../lib/api-server';
import { getMe } from '../../lib/getMe';
import ProUpgradeHint from '../../components/plan/ProUpgradeHint';
import { PRO_COPY, PRO_TRIAL_HREF } from '../../constants/pro';
import { IVD_CATEGORY_ZH, labelFrom } from '../../constants/display';
import PaginationControls from '../../components/PaginationControls';

type PageParams = {
  q?: string;
  company?: string;
  reg_no?: string;
  status?: string;
  class_prefix?: string;
  ivd_category?: string;
  page?: string;
  page_size?: string;
  sort_by?: 'updated_at' | 'approved_date' | 'expiry_date' | 'name';
  sort_order?: 'asc' | 'desc';
};

type ProductListData = {
  total: number;
  page: number;
  page_size: number;
  sort_by: string;
  sort_order: string;
  items: Array<{
    product: {
      id: string;
      name: string;
      reg_no?: string | null;
      udi_di: string;
      status: string;
      class_name?: string | null;
      ivd_category?: string | null;
      approved_date?: string | null;
      expiry_date?: string | null;
      company?: { id: string; name: string } | null;
    };
  }>;
};

function sortByLabel(v: string): string {
  const m: Record<string, string> = {
    updated_at: '最近更新',
    approved_date: '批准日期',
    expiry_date: '失效日期',
    name: '产品名称',
  };
  return m[v] || v;
}

function sortOrderLabel(v: string): string {
  return v === 'asc' ? '升序' : v === 'desc' ? '降序' : v;
}

export default async function LibraryPage({ searchParams }: { searchParams: Promise<PageParams> }) {
  const API_BASE = apiBase();
  const cookie = (await headers()).get('cookie') || '';
  const authRes = await fetch(`${API_BASE}/api/auth/me`, {
    method: 'GET',
    headers: cookie ? { cookie } : undefined,
    cache: 'no-store',
  });
  if (authRes.status === 401) redirect('/login');

  const me = await getMe();
  const isPro = Boolean(me?.plan?.is_pro || me?.plan?.is_admin);
  const params = await searchParams;
  const page = Number(params.page || '1');
  const pageSize = Number(params.page_size || '30');
  const sortBy = params.sort_by || 'updated_at';
  const sortOrder = params.sort_order || 'desc';

  const query = qs({
    q: params.q,
    company: params.company,
    reg_no: params.reg_no,
    status: params.status,
    class_prefix: params.class_prefix,
    ivd_category: params.ivd_category,
    page,
    page_size: pageSize,
    sort_by: sortBy,
    sort_order: sortOrder,
  });

  const res = isPro ? await apiGet<ProductListData>(`/api/products/full${query}`) : { data: null, error: null };
  const exportHref = `/api/export/search.csv${qs({ q: params.q, company: params.company, reg_no: params.reg_no })}`;

  return (
    <div className="grid">
      <Card>
        <CardHeader>
          <CardTitle>完整产品库</CardTitle>
          <CardDescription>Pro 全量视图，仅展示 IVD 范围产品（22 / 6840 / 07(IVD) / 21(IVD)）。</CardDescription>
        </CardHeader>
        <CardContent>
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center', marginBottom: 10 }}>
            {isPro ? (
              <>
                <a className="ui-btn" href={exportHref}>
                  导出 CSV
                </a>
                <Badge variant="success">Pro</Badge>
              </>
            ) : (
              <ProUpgradeHint text={PRO_COPY.search_free_hint} ctaHref={PRO_TRIAL_HREF} />
            )}
          </div>

          <form className="controls" method="GET">
            <Input name="q" defaultValue={params.q} placeholder="关键词（产品名/注册证号/UDI-DI）" />
            <Input name="company" defaultValue={params.company} placeholder="企业名称" />
            <Input name="reg_no" defaultValue={params.reg_no} placeholder="注册证号" />
            <Select name="status" defaultValue={params.status || ''}>
              <option value="">全部状态</option>
              <option value="active">有效</option>
              <option value="cancelled">已注销</option>
              <option value="expired">已过期</option>
            </Select>
            <Select name="ivd_category" defaultValue={params.ivd_category || ''}>
              <option value="">全部类别</option>
              <option value="reagent">试剂</option>
              <option value="instrument">仪器</option>
              <option value="software">软件</option>
            </Select>
            <Input name="class_prefix" defaultValue={params.class_prefix} placeholder="分类码前缀（例:22/6840/07/21）" />
            <Select name="sort_by" defaultValue={sortBy}>
              <option value="updated_at">最近更新</option>
              <option value="approved_date">批准日期</option>
              <option value="expiry_date">失效日期</option>
              <option value="name">产品名称</option>
            </Select>
            <Select name="sort_order" defaultValue={sortOrder}>
              <option value="desc">降序</option>
              <option value="asc">升序</option>
            </Select>
            <Input name="page_size" defaultValue={String(pageSize)} placeholder="每页数量" inputMode="numeric" />
            <Button type="submit">查询</Button>
          </form>
        </CardContent>
      </Card>

      {!isPro ? null : res.error ? (
        <ErrorState text={`加载失败：${res.error}`} />
      ) : !res.data ? (
        <EmptyState text="暂无数据" />
      ) : (
        <>
          {(() => {
            const totalPages = Math.max(1, Math.ceil((res.data?.total || 0) / Math.max(1, pageSize)));
            return (
          <Card>
            <CardContent style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
              <Badge variant="muted">共 {res.data.total} 条</Badge>
              <span className="muted">
                第 {res.data.page} / {totalPages} 页（每页 {res.data.page_size} 条） / 排序：{sortByLabel(res.data.sort_by)}（{sortOrderLabel(res.data.sort_order)}）
              </span>
            </CardContent>
          </Card>
            );
          })()}

          {res.data.items.length === 0 ? (
            <EmptyState text="暂无匹配结果" />
          ) : (
            <div className="list">
              {res.data.items.map((item) => (
                <Card key={item.product.id}>
                  <CardHeader>
                    <CardTitle>
                      <Link href={`/products/${item.product.id}`}>{item.product.name}</Link>
                    </CardTitle>
                    <CardDescription>
                      <span className="muted">UDI-DI:</span> {item.product.udi_di}
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="grid">
                    <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
                      <Badge variant="muted">注册证号: {item.product.reg_no || '-'}</Badge>
                      <Badge variant="muted">分类码: {item.product.class_name || '-'}</Badge>
                      <Badge variant="muted">IVD类别: {labelFrom(IVD_CATEGORY_ZH, item.product.ivd_category)}</Badge>
                      <Badge variant="muted">批准日期: {item.product.approved_date || '-'}</Badge>
                      <Badge variant="muted">失效日期: {item.product.expiry_date || '-'}</Badge>
                    </div>
                    <div>
                      <span className="muted">企业:</span>{' '}
                      {item.product.company ? (
                        <Link href={`/companies/${item.product.company.id}`}>{item.product.company.name}</Link>
                      ) : (
                        '-'
                      )}
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}

          <Card>
            <CardContent style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
              <PaginationControls
                basePath="/library"
                params={{
                  q: params.q,
                  company: params.company,
                  reg_no: params.reg_no,
                  status: params.status,
                  class_prefix: params.class_prefix,
                  ivd_category: params.ivd_category,
                  sort_by: sortBy,
                  sort_order: sortOrder,
                }}
                page={page}
                pageSize={pageSize}
                total={res.data.total}
              />
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
