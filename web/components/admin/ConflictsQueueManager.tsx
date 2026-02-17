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
import { Textarea } from '../ui/textarea';
import { toast } from '../ui/use-toast';
import { ADMIN_CONFLICT_STATUS_ZH } from '../../constants/admin-i18n';

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

type ConflictGroupedItem = {
  registration_no: string;
  conflict_count: number;
  fields: string[];
  latest_created_at?: string | null;
  top_sources: string[];
};

type ListResp = {
  code: number;
  message: string;
  data?: { items: ConflictItem[]; count: number; status: string; group_by?: string };
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
    reason?: string;
  };
};

const DEFAULT_LIMIT = 200;

function conflictStatusBadgeVariant(status: string): 'muted' | 'success' | 'warning' | 'danger' {
  const s = String(status || '').toLowerCase();
  if (s === 'open') return 'danger';
  if (s === 'resolved') return 'success';
  return 'muted';
}

export default function ConflictsQueueManager({ initialItems }: { initialItems: ConflictItem[] }) {
  const [items, setItems] = useState<ConflictItem[]>(initialItems || []);
  const [groupedItems, setGroupedItems] = useState<ConflictGroupedItem[]>([]);
  const [status, setStatus] = useState<string>('open');
  const [viewMode, setViewMode] = useState<'grouped' | 'raw-list'>('grouped');
  const [loading, setLoading] = useState(false);
  const [submittingId, setSubmittingId] = useState<string | null>(null);
  const [winnerInputById, setWinnerInputById] = useState<Record<string, string>>({});
  const [winnerSourceById, setWinnerSourceById] = useState<Record<string, string>>({});
  const [reasonById, setReasonById] = useState<Record<string, string>>({});
  const [errorById, setErrorById] = useState<Record<string, string>>({});
  const [query, setQuery] = useState('');

  const filteredRaw = useMemo(() => {
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
  const filteredGrouped = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return groupedItems;
    return groupedItems.filter((x) => {
      return (
        (x.registration_no || '').toLowerCase().includes(q) ||
        (x.fields || []).some((f) => (f || '').toLowerCase().includes(q)) ||
        (x.top_sources || []).some((s) => (s || '').toLowerCase().includes(q))
      );
    });
  }, [groupedItems, query]);

  const groupedDetailByReg = useMemo(() => {
    const map = new Map<string, ConflictItem[]>();
    for (const it of items) {
      const k = String(it.registration_no || '').trim();
      if (!k) continue;
      const prev = map.get(k) || [];
      prev.push(it);
      map.set(k, prev);
    }
    return map;
  }, [items]);

  function formatApiError(body: unknown, fallback: string): string {
    if (!body || typeof body !== 'object') return fallback;
    const obj = body as Record<string, unknown>;
    const code = obj.code ? String(obj.code) : '';
    const msg = obj.message ? String(obj.message) : '';
    const detail = obj.detail;
    if (detail && typeof detail === 'object') {
      const d = detail as Record<string, unknown>;
      const dc = d.code ? String(d.code) : '';
      const dm = d.message ? String(d.message) : '';
      return [dc, dm].filter(Boolean).join(' - ') || fallback;
    }
    if (typeof detail === 'string' && detail) {
      return [code, msg, detail].filter(Boolean).join(' - ');
    }
    return [code, msg].filter(Boolean).join(' - ') || fallback;
  }

  async function fetchList(
    path: string,
    st: string,
    mode: 'grouped' | 'raw-list'
  ): Promise<NonNullable<ListResp['data']>> {
    const params = new URLSearchParams();
    params.set('status', st);
    params.set('limit', String(DEFAULT_LIMIT));
    if (mode === 'grouped') params.set('group_by', 'registration_no');
    const res = await fetch(`${path}?${params.toString()}`, {
      credentials: 'include',
      cache: 'no-store',
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(formatApiError(body, `HTTP ${res.status}`));
    }
    const body = (await res.json()) as ListResp;
    if (body.code !== 0 || !body.data) throw new Error(formatApiError(body, body.message || '加载冲突列表失败'));
    return body.data as NonNullable<ListResp['data']>;
  }

  async function refresh(nextStatus?: string, nextView?: 'grouped' | 'raw-list') {
    const st = (nextStatus || status || 'open').toLowerCase();
    const mode = nextView || viewMode;
    setLoading(true);
    try {
      try {
        const data = await fetchList('/api/admin/conflicts', st, mode);
        if (mode === 'grouped') {
          setGroupedItems((data.items as unknown as ConflictGroupedItem[]) || []);
          const rawData = await fetchList('/api/admin/conflicts', st, 'raw-list');
          setItems((rawData.items as unknown as ConflictItem[]) || []);
        } else {
          setItems((data.items as unknown as ConflictItem[]) || []);
        }
      } catch {
        const fallbackData = await fetchList('/api/admin/conflicts-queue', st, 'raw-list');
        const rawItems = (fallbackData.items as unknown as ConflictItem[]) || [];
        setItems(rawItems);
        if (mode === 'grouped') {
          const agg = new Map<string, ConflictGroupedItem>();
          for (const it of rawItems) {
            const reg = String(it.registration_no || '').trim();
            if (!reg) continue;
            const cur = agg.get(reg) || {
              registration_no: reg,
              conflict_count: 0,
              fields: [],
              latest_created_at: null,
              top_sources: [],
            };
            cur.conflict_count += 1;
            if (!cur.fields.includes(it.field_name)) cur.fields.push(it.field_name);
            if (!cur.latest_created_at || (it.created_at && it.created_at > cur.latest_created_at)) {
              cur.latest_created_at = it.created_at || cur.latest_created_at;
            }
            for (const c of it.candidates || []) {
              const src = String(c.source_key || '').trim();
              if (src && !cur.top_sources.includes(src)) cur.top_sources.push(src);
            }
            agg.set(reg, cur);
          }
          setGroupedItems(Array.from(agg.values()).sort((a, b) => String(b.latest_created_at || '').localeCompare(String(a.latest_created_at || ''))));
        }
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
      toast({ variant: 'destructive', title: '缺少裁决值', description: '请先输入裁决值（winner_value）' });
      return;
    }
    const reason = (reasonById[item.id] || '').trim();
    if (!reason) {
      const msg = 'E_REASON_REQUIRED - 原因必填';
      setErrorById((prev) => ({ ...prev, [item.id]: msg }));
      toast({ variant: 'destructive', title: '缺少 reason', description: msg });
      return;
    }
    const winnerSource = (winnerSourceById[item.id] || 'MANUAL').trim() || 'MANUAL';
    setSubmittingId(item.id);
    setErrorById((prev) => ({ ...prev, [item.id]: '' }));
    try {
      let res = await fetch(`/api/admin/conflicts/${encodeURIComponent(item.id)}/resolve`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ winner_value: winnerValue, winner_source_key: winnerSource, reason }),
      });
      if (res.status === 404) {
        res = await fetch(`/api/admin/conflicts-queue/${encodeURIComponent(item.id)}/resolve`, {
          method: 'POST',
          credentials: 'include',
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify({ winner_value: winnerValue, winner_source_key: winnerSource, reason }),
        });
      }
      const body = (await res.json().catch(() => ({}))) as ResolveResp;
      if (!res.ok || body.code !== 0 || !body.data) {
        const msg = formatApiError(body, `HTTP ${res.status}`);
        setErrorById((prev) => ({ ...prev, [item.id]: msg }));
        throw new Error(msg);
      }
      toast({ title: '裁决成功', description: `${body.data.registration_no} · ${body.data.field_name} 已更新` });
      await refresh(status, viewMode);
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
              void refresh(next, viewMode);
            }}
            style={{ minWidth: 180 }}
          >
            <option value="open">open（{ADMIN_CONFLICT_STATUS_ZH.open}）</option>
            <option value="resolved">resolved（{ADMIN_CONFLICT_STATUS_ZH.resolved}）</option>
            <option value="all">all（{ADMIN_CONFLICT_STATUS_ZH.all}）</option>
          </Select>
          <Select
            value={viewMode}
            onChange={(e) => {
              const nextMode = (String(e.target.value || 'grouped') as 'grouped' | 'raw-list');
              setViewMode(nextMode);
              void refresh(status, nextMode);
            }}
            style={{ minWidth: 180 }}
          >
            <option value="grouped">按注册证汇总（默认）</option>
            <option value="raw-list">原始列表</option>
          </Select>
          <Input
            placeholder="按注册证号 / 字段名过滤"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            style={{ minWidth: 320 }}
          />
          <Button onClick={() => void refresh()} disabled={loading}>
            {loading ? '刷新中...' : '刷新'}
          </Button>
          <Badge variant="muted">显示数量: {viewMode === 'grouped' ? filteredGrouped.length : filteredRaw.length}</Badge>
          <Badge variant="warning">裁决需填写原因（会写入审计）</Badge>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>待处理冲突</CardTitle></CardHeader>
        <CardContent>
          {loading ? (
            <Skeleton style={{ height: 96 }} />
          ) : (viewMode === 'grouped' ? filteredGrouped.length === 0 : filteredRaw.length === 0) ? (
            <EmptyState text="当前条件下没有冲突记录" />
          ) : viewMode === 'grouped' ? (
            <div className="grid" style={{ gap: 10 }}>
              {filteredGrouped.map((grp) => {
                const details = groupedDetailByReg.get(grp.registration_no) || [];
                return (
                  <div key={grp.registration_no} className="card">
                    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
                      <Badge variant="muted">{grp.registration_no}</Badge>
                      <Badge variant="warning">冲突数: {grp.conflict_count}</Badge>
                      <Badge variant="muted">最近: {grp.latest_created_at || '-'}</Badge>
                      {(grp.top_sources || []).slice(0, 5).map((s) => (
                        <Badge key={`${grp.registration_no}-${s}`} variant="muted">{s}</Badge>
                      ))}
                    </div>
                    <div style={{ marginTop: 8, display: 'grid', gap: 8 }}>
                      {details.map((it) => (
                        <div key={it.id} className="card" style={{ padding: 10 }}>
                          <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                            <Badge variant="muted">{it.field_name}</Badge>
                            <Badge variant={conflictStatusBadgeVariant(it.status)}>{it.status}</Badge>
                            <span className="muted">候选：</span>
                            {(it.candidates || []).slice(0, 3).map((c, idx) => (
                              <span key={`${it.id}-${idx}`} style={{ fontSize: 12 }}>
                                {c.source_key || '未知源'}: {c.value || '-'}
                              </span>
                            ))}
                          </div>
                          <div style={{ marginTop: 8, display: 'grid', gap: 8 }}>
                            <Input
                              placeholder="裁决值（winner_value）"
                              value={winnerInputById[it.id] || ''}
                              onChange={(e) => setWinnerInputById((prev) => ({ ...prev, [it.id]: e.target.value }))}
                            />
                            <Input
                              placeholder="裁决来源（winner_source_key，默认 MANUAL）"
                              value={winnerSourceById[it.id] || ''}
                              onChange={(e) => setWinnerSourceById((prev) => ({ ...prev, [it.id]: e.target.value }))}
                            />
                            <Textarea
                              placeholder="裁决原因（reason，必填，会写入审计）"
                              value={reasonById[it.id] || ''}
                              onChange={(e) => setReasonById((prev) => ({ ...prev, [it.id]: e.target.value }))}
                            />
                            {errorById[it.id] ? (
                              <div className="muted" style={{ color: 'var(--danger)' }}>{errorById[it.id]}</div>
                            ) : null}
                            <div>
                              <Button onClick={() => void resolveOne(it)} disabled={submittingId === it.id || it.status === 'resolved'}>
                                {submittingId === it.id ? '提交中...' : '裁决'}
                              </Button>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <TableWrap>
              <Table>
                <thead>
                  <tr>
                    <th>注册证号</th>
                    <th>字段</th>
                    <th>候选</th>
                    <th>裁决</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredRaw.map((it) => (
                    <tr key={it.id}>
                      <td>{it.registration_no}</td>
                      <td>
                        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                          <Badge variant="muted">{it.field_name}</Badge>
                          <Badge variant={conflictStatusBadgeVariant(it.status)}>{it.status}</Badge>
                        </div>
                      </td>
                      <td>
                        {(it.candidates || []).slice(0, 3).map((c, idx) => (
                          <div key={`${it.id}-${idx}`} style={{ fontSize: 12, marginBottom: 4 }}>
                            <span>{c.source_key || '未知源'}: </span>
                            <span>{c.value || '-'}</span>
                          </div>
                        ))}
                      </td>
                      <td>
                        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                          <Input
                            placeholder="裁决值（winner_value）"
                            value={winnerInputById[it.id] || ''}
                            onChange={(e) => setWinnerInputById((prev) => ({ ...prev, [it.id]: e.target.value }))}
                            style={{ minWidth: 220 }}
                          />
                          <Input
                            placeholder="裁决来源（winner_source_key，默认 MANUAL）"
                            value={winnerSourceById[it.id] || ''}
                            onChange={(e) => setWinnerSourceById((prev) => ({ ...prev, [it.id]: e.target.value }))}
                            style={{ minWidth: 220 }}
                          />
                          <Input
                            placeholder="裁决原因（reason，必填）"
                            value={reasonById[it.id] || ''}
                            onChange={(e) => setReasonById((prev) => ({ ...prev, [it.id]: e.target.value }))}
                            style={{ minWidth: 260 }}
                          />
                          <Button onClick={() => void resolveOne(it)} disabled={submittingId === it.id || it.status === 'resolved'}>
                            {submittingId === it.id ? '提交中...' : '裁决'}
                          </Button>
                        </div>
                        {errorById[it.id] ? (
                          <div className="muted" style={{ color: 'var(--danger)', marginTop: 6 }}>{errorById[it.id]}</div>
                        ) : null}
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
