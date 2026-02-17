'use client';

import Link from 'next/link';
import { useMemo, useState } from 'react';

import { EmptyState } from '../States';
import { Badge } from '../ui/badge';
import { Button } from '../ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card';
import { Input } from '../ui/input';
import { Select } from '../ui/select';
import { Skeleton } from '../ui/skeleton';
import { Table, TableWrap } from '../ui/table';
import { toast } from '../ui/use-toast';

type PendingRecordItem = {
  id: string;
  source_key: string;
  reason_code: string;
  status: string;
  created_at?: string | null;
  candidate_registry_no?: string | null;
  candidate_company?: string | null;
  candidate_product_name?: string | null;
  raw_document_id: string;
};

type PendingListResp = {
  code: number;
  message: string;
  data?: {
    items: PendingRecordItem[];
    count: number;
    total?: number;
    limit?: number;
    offset?: number;
    order_by?: string;
  };
};

type PendingStatsResp = {
  code: number;
  message: string;
  data?: {
    by_source_key: Array<{ source_key: string; open: number; resolved: number; ignored: number }>;
    by_reason_code: Array<{ reason_code: string; open: number }>;
    backlog: {
      open_total: number;
      resolved_last_24h: number;
      resolved_last_7d: number;
      windows: { resolved_24h_hours: number; resolved_7d_days: number };
    };
  };
};

const PAGE_SIZE = 50;

export default function PendingRecordsManager({
  initialItems,
  initialTotal,
  initialStats,
}: {
  initialItems: PendingRecordItem[];
  initialTotal: number;
  initialStats: PendingStatsResp['data'] | null;
}) {
  const [items, setItems] = useState<PendingRecordItem[]>(initialItems || []);
  const [total, setTotal] = useState<number>(initialTotal || 0);
  const [stats, setStats] = useState<PendingStatsResp['data'] | null>(initialStats || null);
  const [status, setStatus] = useState<string>('open');
  const [sourceKey, setSourceKey] = useState<string>('');
  const [reasonCode, setReasonCode] = useState<string>('');
  const [query, setQuery] = useState<string>('');
  const [offset, setOffset] = useState<number>(0);
  const [loading, setLoading] = useState(false);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return items;
    return items.filter((x) => {
      return (
        (x.source_key || '').toLowerCase().includes(q) ||
        (x.reason_code || '').toLowerCase().includes(q) ||
        (x.candidate_company || '').toLowerCase().includes(q) ||
        (x.candidate_product_name || '').toLowerCase().includes(q) ||
        (x.candidate_registry_no || '').toLowerCase().includes(q)
      );
    });
  }, [items, query]);

  async function refreshStats() {
    const res = await fetch('/api/admin/pending/stats', {
      credentials: 'include',
      cache: 'no-store',
    });
    if (!res.ok) {
      const detail = await res.text();
      throw new Error(detail || `HTTP ${res.status}`);
    }
    const body = (await res.json()) as PendingStatsResp;
    if (body.code !== 0 || !body.data) throw new Error(body.message || '加载统计失败');
    setStats(body.data);
  }

  async function refresh(nextOffset?: number) {
    const useOffset = Math.max(0, nextOffset ?? offset);
    setLoading(true);
    try {
      const params = new URLSearchParams();
      params.set('status', status);
      params.set('limit', String(PAGE_SIZE));
      params.set('offset', String(useOffset));
      params.set('order_by', 'created_at desc');
      if (sourceKey.trim()) params.set('source_key', sourceKey.trim());
      if (reasonCode.trim()) params.set('reason_code', reasonCode.trim());

      const res = await fetch(`/api/admin/pending?${params.toString()}`, {
        credentials: 'include',
        cache: 'no-store',
      });
      if (!res.ok) {
        const detail = await res.text();
        throw new Error(detail || `HTTP ${res.status}`);
      }
      const body = (await res.json()) as PendingListResp;
      if (body.code !== 0 || !body.data) throw new Error(body.message || '加载列表失败');
      setItems(body.data.items || []);
      setTotal(Number(body.data.total ?? body.data.count ?? 0));
      setOffset(useOffset);
      await refreshStats();
    } catch (e) {
      toast({ variant: 'destructive', title: '刷新失败', description: String((e as Error)?.message || e) });
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="grid">
      <Card>
        <CardHeader>
          <CardTitle>Pending 统计</CardTitle>
          <CardDescription>基于 `/api/admin/pending/stats` 的 backlog/source/reason 聚合。</CardDescription>
        </CardHeader>
        <CardContent style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
          <Badge variant="muted">Open 总数: {Number(stats?.backlog?.open_total || 0)}</Badge>
          <Badge variant="muted">24h 已处理: {Number(stats?.backlog?.resolved_last_24h || 0)}</Badge>
          <Badge variant="muted">7d 已处理: {Number(stats?.backlog?.resolved_last_7d || 0)}</Badge>
          <Button onClick={() => void refresh()} disabled={loading}>
            {loading ? '刷新中...' : '刷新统计+列表'}
          </Button>
        </CardContent>
        <CardContent style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
          <div style={{ minWidth: 360, flex: 1 }}>
            <div className="muted" style={{ marginBottom: 6 }}>
              by_source_key
            </div>
            {(stats?.by_source_key || []).slice(0, 8).map((x) => (
              <div key={x.source_key} style={{ fontSize: 13, marginBottom: 4 }}>
                <b>{x.source_key}</b> · open {x.open} / resolved {x.resolved} / ignored {x.ignored}
                <span className="muted"> · </span>
                <Link
                  href={`/admin/data-sources?source_key=${encodeURIComponent(x.source_key)}`}
                  className="muted"
                  style={{ textDecoration: 'underline' }}
                >
                  打开数据源配置
                </Link>
              </div>
            ))}
          </div>
          <div style={{ minWidth: 320, flex: 1 }}>
            <div className="muted" style={{ marginBottom: 6 }}>
              by_reason_code (open)
            </div>
            {(stats?.by_reason_code || []).slice(0, 8).map((x) => (
              <div key={x.reason_code} style={{ fontSize: 13, marginBottom: 4 }}>
                <b>{x.reason_code || '(empty)'}</b> · {x.open}
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Pending 列表</CardTitle>
        </CardHeader>
        <CardContent style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
          <Select
            value={status}
            onChange={(e) => {
              const v = String(e.target.value || 'open').toLowerCase();
              setStatus(v);
              setOffset(0);
            }}
            style={{ minWidth: 180 }}
          >
            <option value="open">open</option>
            <option value="resolved">resolved</option>
            <option value="ignored">ignored</option>
            <option value="pending">pending</option>
            <option value="all">all</option>
          </Select>
          <Input
            placeholder="source_key"
            value={sourceKey}
            onChange={(e) => {
              setSourceKey(e.target.value);
              setOffset(0);
            }}
            style={{ minWidth: 220 }}
          />
          <Input
            placeholder="reason_code"
            value={reasonCode}
            onChange={(e) => {
              setReasonCode(e.target.value);
              setOffset(0);
            }}
            style={{ minWidth: 220 }}
          />
          <Input
            placeholder="列表内关键词过滤"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            style={{ minWidth: 260 }}
          />
          <Button onClick={() => void refresh(0)} disabled={loading}>
            查询
          </Button>
          <Badge variant="muted">
            共 {total} 条 · 当前 {filtered.length} 条
          </Badge>
        </CardContent>
        <CardContent style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          <Button
            variant="secondary"
            disabled={loading || offset <= 0}
            onClick={() => void refresh(Math.max(0, offset - PAGE_SIZE))}
          >
            上一页
          </Button>
          <Button
            variant="secondary"
            disabled={loading || offset + PAGE_SIZE >= total}
            onClick={() => void refresh(offset + PAGE_SIZE)}
          >
            下一页
          </Button>
          <span className="muted">offset={offset}, limit={PAGE_SIZE}</span>
        </CardContent>
        <CardContent>
          {loading ? (
            <Skeleton style={{ height: 96 }} />
          ) : filtered.length === 0 ? (
            <EmptyState text="当前条件下没有记录" />
          ) : (
            <TableWrap>
              <Table>
                <thead>
                  <tr>
                    <th>source_key</th>
                    <th>reason_code</th>
                    <th>status</th>
                    <th>候选信息</th>
                    <th>created_at</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((it) => (
                    <tr key={it.id}>
                      <td>
                        <Link
                          href={`/admin/data-sources?source_key=${encodeURIComponent(it.source_key)}`}
                          className="muted"
                          style={{ textDecoration: 'underline' }}
                        >
                          {it.source_key}
                        </Link>
                      </td>
                      <td>{it.reason_code}</td>
                      <td>
                        <Badge variant="muted">{it.status}</Badge>
                      </td>
                      <td>
                        <div>{it.candidate_product_name || '-'}</div>
                        <div className="muted" style={{ fontSize: 12 }}>{it.candidate_company || '-'}</div>
                        <div className="muted" style={{ fontSize: 12 }}>{it.candidate_registry_no || '-'}</div>
                      </td>
                      <td>{it.created_at || '-'}</td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            </TableWrap>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
