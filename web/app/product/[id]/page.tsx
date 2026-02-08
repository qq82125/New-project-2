const API = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

async function getProduct(id: string) {
  const res = await fetch(`${API}/product/${id}`, { cache: 'no-store' });
  if (!res.ok) return null;
  return res.json();
}

export default async function ProductDetail({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const product = await getProduct(id);
  if (!product) return <div className="card">产品不存在</div>;

  return (
    <div className="card">
      <h2>{product.name}</h2>
      <p>DI: {product.udi_di}</p>
      <p>型号: {product.model || '-'}</p>
      <p>规格: {product.specification || '-'}</p>
      <p>分类: {product.category || '-'}</p>
      <p>企业: {product.company?.name || '-'}</p>
      <p>注册证号: {product.registration?.registration_no || '-'}</p>
    </div>
  );
}
