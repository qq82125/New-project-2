import Link from 'next/link';
import { EmptyState, ErrorState } from '../../../components/States';
import { apiGet } from '../../../lib/api';

type CompanyData = {
  id: string;
  name: string;
  country?: string | null;
};

export default async function CompanyDetailPage({ params }: { params: Promise<{ id: string }> }) {
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
      <div className="card">
        <h2>{res.data.name}</h2>
        <p>country: {res.data.country || '-'}</p>
        <p>id: {res.data.id}</p>
      </div>
      <div className="card">
        <Link href={`/search?company=${encodeURIComponent(res.data.name)}`}>查看该企业相关产品</Link>
      </div>
    </div>
  );
}
