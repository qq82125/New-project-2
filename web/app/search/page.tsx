import { headers } from 'next/headers';
import { redirect } from 'next/navigation';
import Link from 'next/link';
import { EmptyState, ErrorState } from '../../components/States';
import { apiGet, qs } from '../../lib/api';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card';
import { Input } from '../../components/ui/input';
import { Select } from '../../components/ui/select';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { formatUdiDiDisplay, labelField, labelSortBy, labelSortOrder, labelStatus } from '../../lib/labelMap';

const API_BASE = process.env.API_BASE_URL || process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

type SearchParams = {
  q?: string;
  company?: string;
  reg_no?: string;
  status?: string;
  page?: string;
  page_size?: string;
  sort_by?: 'updated_at' | 'approved_date' | 'expiry_date' | 'name';
  sort_order?: 'asc' | 'desc';
};

type SearchData = {
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
      company?: { id: string; name: string } | null;
      expiry_date?: string | null;
    };
  }>;
};

export default async function SearchPage({ searchParams }: { searchParams: Promise<SearchParams> }) {
  const cookie = (await headers()).get('cookie') || '';
  const meRes = await fetch(`${API_BASE}/api/auth/me`, {
    method: 'GET',
    headers: cookie ? { cookie } : undefined,
    cache: 'no-store',
  });
  if (meRes.status === 401) redirect('/login');

  const params = await searchParams;
  const page = Number(params.page || '1');
  const pageSize = Number(params.page_size || '20');
  const sortBy = params.sort_by || 'updated_at';
  const sortOrder = params.sort_order || 'desc';

  const query = qs({
    q: params.q,
    company: params.company,
    reg_no: params.reg_no,
    status: params.status,
    page,
    page_size: pageSize,
    sort_by: sortBy,
    sort_order: sortOrder,
  });

  const res = await apiGet<SearchData>(`/api/search${query}`);

  return (
    <div className="grid">
      <Card>
        <CardHeader>
          <CardTitle>搜索</CardTitle>
          <CardDescription>按关键词、企业、注册证号等筛选产品。</CardDescription>
        </CardHeader>
        <CardContent>
          <form className="controls" method="GET">
            <Input name="q" defaultValue={params.q} placeholder="关键词（产品名/reg_no/udi_di）" />
            <Input name="company" defaultValue={params.company} placeholder="企业名称" />
            <Input name="reg_no" defaultValue={params.reg_no} placeholder="注册证号" />
            <Select name="status" defaultValue={params.status || ''}>
          <option value="">全部状态</option>
          <option value="active">{labelStatus('active')}</option>
          <option value="cancelled">{labelStatus('cancelled')}</option>
          <option value="expired">{labelStatus('expired')}</option>
            </Select>
            <Select name="sort_by" defaultValue={sortBy}>
          <option value="updated_at">{labelSortBy('updated_at')}</option>
          <option value="approved_date">{labelSortBy('approved_date')}</option>
          <option value="expiry_date">{labelSortBy('expiry_date')}</option>
          <option value="name">{labelSortBy('name')}</option>
            </Select>
            <Select name="sort_order" defaultValue={sortOrder}>
          <option value="desc">{labelSortOrder('desc')}</option>
          <option value="asc">{labelSortOrder('asc')}</option>
            </Select>
            <Button type="submit">搜索</Button>
          </form>
        </CardContent>
      </Card>

      {res.error ? (
        <ErrorState text={`搜索失败：${res.error}`} />
      ) : !res.data ? (
        <EmptyState text="暂无结果" />
      ) : (
        <>
          <Card>
            <CardContent style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
              <Badge variant="muted">共 {res.data.total} 条</Badge>
              <span className="muted">
                第 {res.data.page} 页 / 每页 {res.data.page_size} 条 / 排序：{labelSortBy(res.data.sort_by)}（{labelSortOrder(res.data.sort_order)}）
              </span>
            </CardContent>
          </Card>
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
                      <span className="muted">{labelField('udi_di')}：</span> {formatUdiDiDisplay(item.product.udi_di)}
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="grid">
                    <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
                      <Badge variant="muted">
                        {labelField('reg_no')}：{item.product.reg_no || '-'}
                      </Badge>
                      <Badge
                        variant={
                          item.product.status === 'active'
                            ? 'success'
                            : item.product.status === 'expired'
                              ? 'warning'
                            : item.product.status === 'cancelled'
                                ? 'danger'
                                : 'muted'
                        }
                      >
                        {labelField('status')}：{labelStatus(item.product.status)}
                      </Badge>
                      <Badge variant="muted">
                        {labelField('expiry_date')}：{item.product.expiry_date || '-'}
                      </Badge>
                    </div>
                    <div>
                      <span className="muted">{labelField('company')}：</span>{' '}
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
            {page > 1 ? (
              <Link
                href={`/search${qs({ ...params, page: page - 1, page_size: pageSize, sort_by: sortBy, sort_order: sortOrder })}`}
              >
                上一页
              </Link>
            ) : (
              <span className="muted">上一页</span>
            )}
            <Link
              href={`/search${qs({ ...params, page: page + 1, page_size: pageSize, sort_by: sortBy, sort_order: sortOrder })}`}
            >
              下一页
            </Link>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
