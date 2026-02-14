'use client';

import { useEffect, useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card';
import { Table, TableWrap } from '../ui/table';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import { Input } from '../ui/input';
import { Skeleton } from '../ui/skeleton';
import { toast } from '../ui/use-toast';
import { EmptyState, ErrorState } from '../States';
import { RUN_STATUS_ZH, labelFrom } from '../../constants/display';

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
  ivd_kept_count?: number;
  non_ivd_skipped_count?: number;
  source_notes?: {
    ivd_classifier_version?: number;
    ingest_filtered_non_ivd?: number;
  } | null;
  started_at: string;
  finished_at?: string | null;
};

type ApiResp<T> = { code: number; message: string; data: T };
type PageData = { items: SourceRun[]; total: number; page: number; page_size: number };

function badgeVariant(status: string): 'success' | 'danger' | 'muted' {
  if (status === 'success') return 'success';
  if (status === 'failed' || status === 'FAILED') return 'danger';
  return 'muted';
}

export default function SyncManager({
  initialItems,
  initialPage = 1,
  initialPageSize = 10,
}: {
  initialItems: SourceRun[];
  initialPage?: number;
  initialPageSize?: number;
}) {
  const [items, setItems] = useState<SourceRun[]>(initialItems);
  const [total, setTotal] = useState<number>(initialItems.length);
  const [page, setPage] = useState<number>(Math.max(1, Number(initialPage || 1)));
  const [pageSize, setPageSize] = useState<number>(Math.max(1, Number(initialPageSize || 10)));
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function refresh(targetPage?: number, targetPageSize?: number) {
    setLoading(true);
    setError(null);
    try {
      const p = Math.max(1, Number(targetPage ?? page));
      const ps = Math.max(1, Number(targetPageSize ?? pageSize));
      const res = await fetch(`/api/admin/source-runs?page=${encodeURIComponent(String(p))}&page_size=${encodeURIComponent(String(ps))}`, {
        credentials: 'include',
        cache: 'no-store',
      });
      if (!res.ok) {
        setError(`加载失败 (${res.status})`);
        return;
      }
      const body = (await res.json()) as ApiResp<PageData>;
      if (body.code !== 0) {
        setError(body.message || '接口返回异常');
        return;
      }
      setItems(body.data.items || []);
      setTotal(Number(body.data.total || 0));
      setPage(Math.max(1, Number(body.data.page || p)));
      setPageSize(Math.max(1, Number(body.data.page_size || ps)));
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
      const res = await fetch(`/api/admin/sync/run`, {
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
    void refresh(page, pageSize);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const totalPages = Math.max(1, Math.ceil(Math.max(0, total) / Math.max(1, pageSize)));

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
          <Button variant="secondary" onClick={() => void refresh()} disabled={loading}>
            刷新记录
          </Button>
          <Badge variant="muted">/api/admin/source-runs</Badge>
        </div>

        <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
          <Badge variant="muted">共 {total} 条</Badge>
          <span className="muted">
            第 {page} / {totalPages} 页（每页 {pageSize} 条）
          </span>
          <span className="muted">|</span>
          <Button type="button" variant="secondary" disabled={loading || page <= 1} onClick={() => void refresh(1, pageSize)}>
            首页
          </Button>
          <Button type="button" variant="secondary" disabled={loading || page <= 1} onClick={() => void refresh(page - 1, pageSize)}>
            上一页
          </Button>
          <Button
            type="button"
            variant="secondary"
            disabled={loading || page >= totalPages}
            onClick={() => void refresh(page + 1, pageSize)}
          >
            下一页
          </Button>
          <Button
            type="button"
            variant="secondary"
            disabled={loading || page >= totalPages}
            onClick={() => void refresh(totalPages, pageSize)}
          >
            末页
          </Button>
          <span className="muted">跳转</span>
          <Input
            value={String(page)}
            onChange={(e) => setPage(Math.max(1, Number(e.target.value || '1')))}
            inputMode="numeric"
            style={{ width: 90 }}
            disabled={loading}
          />
          <Button type="button" variant="secondary" disabled={loading} onClick={() => void refresh(page, pageSize)}>
            前往
          </Button>
          <span className="muted">每页</span>
          <Input
            value={String(pageSize)}
            onChange={(e) => setPageSize(Math.max(1, Number(e.target.value || '10')))}
            inputMode="numeric"
            style={{ width: 90 }}
            disabled={loading}
          />
          <Button type="button" variant="secondary" disabled={loading} onClick={() => void refresh(1, pageSize)}>
            应用
          </Button>
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
                  <th style={{ width: 220 }}>IVD过滤</th>
                  <th>信息</th>
                </tr>
              </thead>
              <tbody>
                {items.map((r) => (
                  <tr key={r.id}>
                    <td>#{r.id}</td>
                    <td>{r.source}</td>
                    <td>
                      <Badge variant={badgeVariant(r.status)}>{labelFrom(RUN_STATUS_ZH, (r.status || '').toLowerCase())}</Badge>
                    </td>
                    <td>{new Date(r.started_at).toLocaleString()}</td>
                    <td>{r.finished_at ? new Date(r.finished_at).toLocaleString() : '-'}</td>
                    <td className="muted">
                      成功 {r.records_success}/{r.records_total}（失败 {r.records_failed}） · 新增 {r.added_count} / 更新 {r.updated_count} / 移除 {r.removed_count}
                    </td>
                    <td className="muted">
                      保留 {r.ivd_kept_count ?? 0} / 跳过 {r.non_ivd_skipped_count ?? 0}
                      <div style={{ fontSize: 12 }}>
                        规则版本 v{r.source_notes?.ivd_classifier_version ?? '-'}
                      </div>
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
