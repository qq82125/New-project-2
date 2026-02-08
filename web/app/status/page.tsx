const API = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

async function getStatus() {
  const res = await fetch(`${API}/status`, { cache: 'no-store' });
  if (!res.ok) return { latest_runs: [] };
  return res.json();
}

export default async function StatusPage() {
  const data = await getStatus();
  return (
    <div className="grid">
      {data.latest_runs.map((run: any) => (
        <div className="card" key={run.id}>
          <h3>{run.source}</h3>
          <p>状态: {run.status}</p>
          <p>包名: {run.package_name || '-'}</p>
          <p>开始: {run.started_at}</p>
          <p>结束: {run.finished_at || '-'}</p>
          <p>信息: {run.message || '-'}</p>
        </div>
      ))}
    </div>
  );
}
