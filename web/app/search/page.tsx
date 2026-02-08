import Link from 'next/link';
import { EmptyState, ErrorState } from '../../components/States';
import { apiGet, qs } from '../../lib/api';

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
      <form className="card controls" method="GET">
        <input name="q" defaultValue={params.q} placeholder="关键词（产品名/reg_no/udi_di）" />
        <input name="company" defaultValue={params.company} placeholder="企业名称" />
        <input name="reg_no" defaultValue={params.reg_no} placeholder="注册证号" />
        <select name="status" defaultValue={params.status || ''}>
          <option value="">全部状态</option>
          <option value="active">active</option>
          <option value="cancelled">cancelled</option>
          <option value="expired">expired</option>
        </select>
        <select name="sort_by" defaultValue={sortBy}>
          <option value="updated_at">updated_at</option>
          <option value="approved_date">approved_date</option>
          <option value="expiry_date">expiry_date</option>
          <option value="name">name</option>
        </select>
        <select name="sort_order" defaultValue={sortOrder}>
          <option value="desc">desc</option>
          <option value="asc">asc</option>
        </select>
        <button type="submit">搜索</button>
      </form>

      {res.error ? (
        <ErrorState text={`搜索失败：${res.error}`} />
      ) : !res.data ? (
        <EmptyState text="暂无结果" />
      ) : (
        <>
          <div className="card">共 {res.data.total} 条</div>
          {res.data.items.length === 0 ? (
            <EmptyState text="暂无匹配结果" />
          ) : (
            <div className="list">
              {res.data.items.map((item) => (
                <div key={item.product.id} className="card">
                  <h3>
                    <Link href={`/products/${item.product.id}`}>{item.product.name}</Link>
                  </h3>
                  <div>reg_no: {item.product.reg_no || '-'}</div>
                  <div>udi_di: {item.product.udi_di}</div>
                  <div>status: {item.product.status}</div>
                  <div>
                    company:{' '}
                    {item.product.company ? (
                      <Link href={`/companies/${item.product.company.id}`}>{item.product.company.name}</Link>
                    ) : (
                      '-'
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}

          <div className="card">
            {page > 1 ? (
              <Link
                href={`/search${qs({ ...params, page: page - 1, page_size: pageSize, sort_by: sortBy, sort_order: sortOrder })}`}
              >
                上一页
              </Link>
            ) : (
              <span className="muted">上一页</span>
            )}
            {' | '}
            <Link
              href={`/search${qs({ ...params, page: page + 1, page_size: pageSize, sort_by: sortBy, sort_order: sortOrder })}`}
            >
              下一页
            </Link>
          </div>
        </>
      )}
    </div>
  );
}
