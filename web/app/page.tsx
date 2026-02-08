import Link from 'next/link';
import { HighlightText } from '../components/HighlightText';

const API = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

type SearchParams = {
  q?: string;
  company?: string;
  registration_no?: string;
  page?: string;
};

async function getResults(params: SearchParams) {
  const search = new URLSearchParams();
  if (params.q) search.set('q', params.q);
  if (params.company) search.set('company', params.company);
  if (params.registration_no) search.set('registration_no', params.registration_no);
  if (params.page) search.set('page', params.page);
  const res = await fetch(`${API}/search?${search.toString()}`, { cache: 'no-store' });
  if (!res.ok) return { total: 0, page: 1, page_size: 20, items: [] };
  return res.json();
}

export default async function Page({ searchParams }: { searchParams: Promise<SearchParams> }) {
  const params = await searchParams;
  const data = await getResults(params);
  const page = Number(params.page || '1');

  return (
    <div className="grid">
      <form className="card controls" method="GET">
        <input name="q" defaultValue={params.q} placeholder="关键词（产品名/型号/DI）" />
        <input name="company" defaultValue={params.company} placeholder="企业名称" />
        <input name="registration_no" defaultValue={params.registration_no} placeholder="注册证号" />
        <button type="submit">搜索</button>
      </form>

      <div className="card">共 {data.total} 条</div>

      {data.items.map((item: any) => (
        <div key={item.product.id} className="card">
          <h3>
            <Link href={`/product/${item.product.id}`}>
              <HighlightText text={item.product.name} q={params.q} />
            </Link>
          </h3>
          <div>DI: {item.product.udi_di}</div>
          <div>型号: {item.product.model || '-'}</div>
          <div>
            企业:{' '}
            {item.product.company ? (
              <Link href={`/company/${item.product.company.id}`}>{item.product.company.name}</Link>
            ) : (
              '-'
            )}
          </div>
        </div>
      ))}

      <div className="card">
        {page > 1 ? (
          <Link href={`/?${new URLSearchParams({ ...params, page: String(page - 1) }).toString()}`}>上一页</Link>
        ) : (
          <span>上一页</span>
        )}
        {' | '}
        <Link href={`/?${new URLSearchParams({ ...params, page: String(page + 1) }).toString()}`}>下一页</Link>
      </div>
    </div>
  );
}
