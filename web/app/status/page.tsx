import { headers } from 'next/headers';
import { redirect } from 'next/navigation';
import { EmptyState, ErrorState } from '../../components/States';
import { apiGet } from '../../lib/api';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';

const API_BASE = process.env.API_BASE_URL || process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

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
  const cookie = (await headers()).get('cookie') || '';
  const meRes = await fetch(`${API_BASE}/api/auth/me`, {
    method: 'GET',
    headers: cookie ? { cookie } : undefined,
    cache: 'no-store',
  });
  if (meRes.status === 401) redirect('/login');

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
        <Card key={run.id}>
          <CardHeader>
            <CardTitle>
              #{run.id} <span className="muted">{run.source}</span>
            </CardTitle>
            <CardDescription>
              <span className="muted">started:</span> {new Date(run.started_at).toLocaleString()}
              {' · '}
              <span className="muted">finished:</span> {run.finished_at ? new Date(run.finished_at).toLocaleString() : '-'}
            </CardDescription>
          </CardHeader>
          <CardContent className="grid">
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
              <Badge variant={run.status === 'success' ? 'success' : run.status === 'failed' ? 'danger' : 'muted'}>
                status: {run.status}
              </Badge>
              <Badge variant="muted">
                records: {run.records_success}/{run.records_total} (failed {run.records_failed})
              </Badge>
              <Badge variant="muted">
                added/updated/removed: {run.added_count}/{run.updated_count}/{run.removed_count}
              </Badge>
            </div>
            <div className="muted">message: {run.message || '-'}</div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
