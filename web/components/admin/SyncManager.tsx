'use client';

import { useEffect, useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card';
import { Table, TableWrap } from '../ui/table';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import { Skeleton } from '../ui/skeleton';
import { toast } from '../ui/use-toast';
import { EmptyState, ErrorState } from '../States';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

type SourceRun = {
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
};

type ApiResp<T> = { code: number; message: string; data: T };

function badgeVariant(status: string): 'success' | 'danger' | 'muted' {
  if (status === 'success') return 'success';
  if (status === 'failed' || status === 'FAILED') return 'danger';
  return 'muted';
}

export default function SyncManager({ initialItems }: { initialItems: SourceRun[] }) {
  const [items, setItems] = useState<SourceRun[]>(initialItems);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/admin/source-runs?limit=50`, {
        credentials: 'include',
        cache: 'no-store',
      });
      if (!res.ok) {
        setError(`加载失败 (${res.status})`);
        return;
      }
      const body = (await res.json()) as ApiResp<{ items: SourceRun[] }>;
      if (body.code !== 0) {
        setError(body.message || '接口返回异常');
        return;
      }
      setItems(body.data.items || []);
    } catch (e) {
      setError(e instanceof Error ? e.message : '网络错误');
    } finally {
      setLoading(false);
    }
  }

  async function runSync() {
    if (!window.confirm('确认要手动触发一次同步吗？这会开始下载、解压并写入数据库。')) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/admin/sync/run`, {
        method: 'POST',
        credentials: 'include',
      });
      if (!res.ok) {
        const msg = `触发失败 (${res.status})`;
        setError(msg);
        toast({ variant: 'destructive', title: '触发同步失败', description: msg });
        return;
      }
      const body = (await res.json()) as ApiResp<{ queued: boolean }>;
      if (body.code !== 0 || !body.data?.queued) {
        const msg = body.message || '触发失败';
        setError(msg);
        toast({ variant: 'destructive', title: '触发同步失败', description: msg });
        return;
      }
      toast({ title: '已触发同步', description: '任务已进入执行（可能需要数分钟）。' });
      await refresh();
      // Pull again shortly to catch the RUNNING record.
      window.setTimeout(() => void refresh(), 1200);
    } catch (e) {
      const msg = e instanceof Error ? e.message : '网络错误';
      setError(msg);
      toast({ variant: 'destructive', title: '网络错误', description: msg });
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <Card>
      <CardHeader>
        <CardTitle>同步控制</CardTitle>
        <CardDescription>查看同步记录，并手动触发同步任务。</CardDescription>
      </CardHeader>
      <CardContent className="grid">
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
          <Button onClick={runSync} disabled={loading}>
            手动触发同步
          </Button>
          <Button variant="secondary" onClick={refresh} disabled={loading}>
            刷新记录
          </Button>
          <Badge variant="muted">/api/admin/source-runs</Badge>
        </div>

        {error ? <ErrorState text={error} /> : null}

        {loading && items.length === 0 ? (
          <div className="grid">
            <Skeleton height={28} />
            <Skeleton height={180} />
          </div>
        ) : items.length === 0 ? (
          <EmptyState text="暂无同步记录" />
        ) : (
          <TableWrap>
            <Table>
              <thead>
                <tr>
                  <th style={{ width: 80 }}>ID</th>
                  <th>来源</th>
                  <th style={{ width: 120 }}>状态</th>
                  <th style={{ width: 180 }}>开始时间</th>
                  <th style={{ width: 180 }}>结束时间</th>
                  <th style={{ width: 220 }}>统计</th>
                  <th>信息</th>
                </tr>
              </thead>
              <tbody>
                {items.map((r) => (
                  <tr key={r.id}>
                    <td>#{r.id}</td>
                    <td>{r.source}</td>
                    <td>
                      <Badge variant={badgeVariant(r.status)}>{r.status}</Badge>
                    </td>
                    <td>{new Date(r.started_at).toLocaleString()}</td>
                    <td>{r.finished_at ? new Date(r.finished_at).toLocaleString() : '-'}</td>
                    <td className="muted">
                      {r.records_success}/{r.records_total} (fail {r.records_failed}) · +{r.added_count} ~{r.updated_count} -{r.removed_count}
                    </td>
                    <td className="muted" style={{ maxWidth: 360 }}>
                      {r.message || '-'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </Table>
          </TableWrap>
        )}
      </CardContent>
    </Card>
  );
}

