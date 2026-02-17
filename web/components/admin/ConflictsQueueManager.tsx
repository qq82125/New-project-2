'use client';

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

type ConflictCandidate = {
  source_key?: string;
  value?: string;
  observed_at?: string;
  evidence_grade?: string;
  source_priority?: number;
};

type ConflictItem = {
  id: string;
  registration_no: string;
  registration_id?: string | null;
  field_name: string;
  candidates: ConflictCandidate[];
  status: string;
  winner_value?: string | null;
  winner_source_key?: string | null;
  source_run_id?: number | null;
  resolved_by?: string | null;
  resolved_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

type ListResp = {
  code: number;
  message: string;
  data?: { items: ConflictItem[]; count: number; status: string };
};

type ResolveResp = {
  code: number;
  message: string;
  data?: {
    id: string;
    registration_no: string;
    field_name: string;
    winner_value: string;
    winner_source_key: string;
    status: string;
  };
};

const DEFAULT_LIMIT = 200;

export default function ConflictsQueueManager({ initialItems }: { initialItems: ConflictItem[] }) {
  const [items, setItems] = useState<ConflictItem[]>(initialItems || []);
  const [status, setStatus] = useState<string>('open');
  const [loading, setLoading] = useState(false);
  const [submittingId, setSubmittingId] = useState<string | null>(null);
  const [winnerInputById, setWinnerInputById] = useState<Record<string, string>>({});
  const [winnerSourceById, setWinnerSourceById] = useState<Record<string, string>>({});
  const [query, setQuery] = useState('');

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return items;
    return items.filter((x) => {
      return (
        (x.registration_no || '').toLowerCase().includes(q) ||
        (x.field_name || '').toLowerCase().includes(q) ||
        (x.winner_value || '').toLowerCase().includes(q)
      );
    });
  }, [items, query]);

  async function fetchList(path: string, st: string): Promise<ConflictItem[]> {
    const res = await fetch(`${path}?status=${encodeURIComponent(st)}&limit=${DEFAULT_LIMIT}`, {
      credentials: 'include',
      cache: 'no-store',
    });
    if (!res.ok) {
      const detail = await res.text();
      throw new Error(detail || `HTTP ${res.status}`);
    }
    const body = (await res.json()) as ListResp;
    if (body.code !== 0 || !body.data) throw new Error(body.message || '加载冲突列表失败');
    return body.data.items || [];
  }

  async function refresh(nextStatus?: string) {
    const st = (nextStatus || status || 'open').toLowerCase();
    setLoading(true);
    try {
      try {
        const rows = await fetchList('/api/admin/conflicts', st);
        setItems(rows);
      } catch {
        const rows = await fetchList('/api/admin/conflicts-queue', st);
        setItems(rows);
      }
    } catch (e) {
      toast({ variant: 'destructive', title: '刷新失败', description: String((e as Error)?.message || e) });
    } finally {
      setLoading(false);
    }
  }

  async function resolveOne(item: ConflictItem) {
    const winnerValue = (winnerInputById[item.id] || '').trim();
    if (!winnerValue) {
      toast({ variant: 'destructive', title: '缺少 winner_value', description: '请先输入裁决值' });
      return;
    }
    const winnerSource = (winnerSourceById[item.id] || 'MANUAL').trim() || 'MANUAL';
    setSubmittingId(item.id);
    try {
      let res = await fetch(`/api/admin/conflicts/${encodeURIComponent(item.id)}/resolve`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ winner_value: winnerValue, winner_source_key: winnerSource }),
      });
      if (res.status === 404) {
        res = await fetch(`/api/admin/conflicts-queue/${encodeURIComponent(item.id)}/resolve`, {
          method: 'POST',
          credentials: 'include',
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify({ winner_value: winnerValue, winner_source_key: winnerSource }),
        });
      }
      const body = (await res.json()) as ResolveResp;
      if (!res.ok || body.code !== 0 || !body.data) throw new Error(body.message || `HTTP ${res.status}`);
      toast({ title: '裁决成功', description: `${body.data.registration_no} · ${body.data.field_name} 已更新` });
      setItems((prev) => prev.filter((x) => x.id !== item.id));
    } catch (e) {
      toast({ variant: 'destructive', title: '裁决失败', description: String((e as Error)?.message || e) });
    } finally {
      setSubmittingId(null);
    }
  }

  return (
    <div className="grid">
      <Card>
        <CardHeader>
          <CardTitle>冲突队列</CardTitle>
          <CardDescription>默认走新接口 `/api/admin/conflicts`，用于处理字段级无法自动裁决的冲突。</CardDescription>
        </CardHeader>
        <CardContent style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
          <Select
            value={status}
            onChange={(e) => {
              const next = String(e.target.value || 'open').toLowerCase();
              setStatus(next);
              void refresh(next);
            }}
            style={{ minWidth: 180 }}
          >
            <option value="open">open</option>
            <option value="resolved">resolved</option>
            <option value="all">all</option>
          </Select>
          <Input
            placeholder="按 registration_no / field_name 过滤"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            style={{ minWidth: 320 }}
          />
          <Button onClick={() => void refresh()} disabled={loading}>
            {loading ? '刷新中...' : '刷新'}
          </Button>
          <Badge variant="muted">显示: {filtered.length}</Badge>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>待处理冲突</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <Skeleton style={{ height: 96 }} />
          ) : filtered.length === 0 ? (
            <EmptyState text="当前条件下没有冲突记录" />
          ) : (
            <TableWrap>
              <Table>
                <thead>
                  <tr>
                    <th>registration_no</th>
                    <th>字段</th>
                    <th>候选</th>
                    <th>裁决</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((it) => (
                    <tr key={it.id}>
                      <td>{it.registration_no}</td>
                      <td>
                        <Badge variant="muted">{it.field_name}</Badge>
                      </td>
                      <td>
                        {(it.candidates || []).slice(0, 3).map((c, idx) => (
                          <div key={`${it.id}-${idx}`} style={{ fontSize: 12, marginBottom: 4 }}>
                            <span>{c.source_key || 'UNKNOWN'}: </span>
                            <span>{c.value || '-'}</span>
                          </div>
                        ))}
                      </td>
                      <td>
                        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                          <Input
                            placeholder="winner_value"
                            value={winnerInputById[it.id] || ''}
                            onChange={(e) => setWinnerInputById((prev) => ({ ...prev, [it.id]: e.target.value }))}
                            style={{ minWidth: 220 }}
                          />
                          <Input
                            placeholder="winner_source_key (默认 MANUAL)"
                            value={winnerSourceById[it.id] || ''}
                            onChange={(e) => setWinnerSourceById((prev) => ({ ...prev, [it.id]: e.target.value }))}
                            style={{ minWidth: 220 }}
                          />
                          <Button onClick={() => void resolveOne(it)} disabled={submittingId === it.id || it.status === 'resolved'}>
                            {submittingId === it.id ? '提交中...' : '裁决'}
                          </Button>
                        </div>
                      </td>
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

