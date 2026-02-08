import Link from 'next/link';
import { EmptyState, ErrorState } from '../../../components/States';
import { apiGet } from '../../../lib/api';

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
      <div className="card">
        <h2>{res.data.name}</h2>
        <p>reg_no: {res.data.reg_no || '-'}</p>
        <p>udi_di: {res.data.udi_di}</p>
        <p>status: {res.data.status}</p>
        <p>approved_date: {res.data.approved_date || '-'}</p>
        <p>expiry_date: {res.data.expiry_date || '-'}</p>
        <p>class: {res.data.class_name || '-'}</p>
        <p>
          company:{' '}
          {res.data.company ? <Link href={`/companies/${res.data.company.id}`}>{res.data.company.name}</Link> : '-'}
        </p>
      </div>
      <div className="card">
        <Link href={`/search?reg_no=${encodeURIComponent(res.data.reg_no || '')}`}>按 reg_no 搜索</Link>
      </div>
    </div>
  );
}
