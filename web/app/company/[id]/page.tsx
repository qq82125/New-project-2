const API = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

async function getCompany(id: string) {
  const res = await fetch(`${API}/company/${id}`, { cache: 'no-store' });
  if (!res.ok) return null;
  return res.json();
}

export default async function CompanyDetail({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const company = await getCompany(id);
  if (!company) return <div className="card">企业不存在</div>;

  return (
    <div className="card">
      <h2>{company.name}</h2>
      <p>国家/地区: {company.country || '-'}</p>
      <p>ID: {company.id}</p>
    </div>
  );
}
