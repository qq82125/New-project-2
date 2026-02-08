import { EmptyState, ErrorState } from '../../components/States';
import { apiGet } from '../../lib/api';

type StatusData = {
  latest_runs: Array<{
    id: number;
    source: string;
    status: string;
    message?: string | null;
    records_total: number;
    records_success: number;
    records_failed: number;
    added_count: number;
    updated_count: number;
    removed_count: number;
    started_at: string;
    finished_at?: string | null;
  }>;
};

export default async function StatusPage() {
  const res = await apiGet<StatusData>('/api/status');

  if (res.error) {
    return <ErrorState text={`状态页加载失败：${res.error}`} />;
  }
  if (!res.data || res.data.latest_runs.length === 0) {
    return <EmptyState text="暂无同步状态数据" />;
  }

  return (
    <div className="grid">
      {res.data.latest_runs.map((run) => (
        <div className="card" key={run.id}>
          <h3>#{run.id} {run.source}</h3>
          <p>status: {run.status}</p>
          <p>records: {run.records_success}/{run.records_total} (failed {run.records_failed})</p>
          <p>added/updated/removed: {run.added_count}/{run.updated_count}/{run.removed_count}</p>
          <p>started_at: {new Date(run.started_at).toLocaleString()}</p>
          <p>finished_at: {run.finished_at ? new Date(run.finished_at).toLocaleString() : '-'}</p>
          <p>message: {run.message || '-'}</p>
        </div>
      ))}
    </div>
  );
}
