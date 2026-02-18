'use client';

import Link from 'next/link';
import { useMemo, useState } from 'react';

import { EmptyState } from '../States';
import { Badge } from '../ui/badge';
import { Button } from '../ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card';
import { Input } from '../ui/input';
import { Modal } from '../ui/modal';
import { Select } from '../ui/select';
import { Skeleton } from '../ui/skeleton';
import { Table, TableWrap } from '../ui/table';
import { Textarea } from '../ui/textarea';
import { toast } from '../ui/use-toast';
import { ADMIN_PENDING_STATUS_ZH } from '../../constants/admin-i18n';

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

function formatApiError(body: unknown, fallback: string): string {
  const unknownError = fallback || '请求失败';
  if (!body || typeof body !== 'object') return unknownError;
  const obj = body as Record<string, unknown>;
  const code = (obj.code ? String(obj.code) : '');
  const message = (obj.message ? String(obj.message) : '');
  const detail = obj.detail;
  if (detail && typeof detail === 'object') {
    const d = detail as Record<string, unknown>;
    const dCode = d.code ? String(d.code) : '';
    const dMsg = d.message ? String(d.message) : '';
    if (dCode || dMsg) return [dCode, dMsg].filter(Boolean).join(' - ');
  }
  if (typeof detail === 'string' && detail.trim()) {
    return [code, message, detail].filter(Boolean).join(' - ');
  }
  if (code || message) return [code, message].filter(Boolean).join(' - ');
  return unknownError;
}

function statusBadgeVariant(status: string): 'muted' | 'success' | 'warning' | 'danger' {
  const s = String(status || '').toLowerCase();
  if (s === 'open' || s === 'pending') return 'warning';
  if (s === 'resolved') return 'success';
  if (s === 'ignored') return 'muted';
  return 'danger';
}

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
  const [detailOpen, setDetailOpen] = useState(false);
  const [selected, setSelected] = useState<PendingRecordItem | null>(null);
  const [resolveRegNo, setResolveRegNo] = useState('');
  const [ignoreReason, setIgnoreReason] = useState('');
  const [actionLoading, setActionLoading] = useState<'' | 'resolve' | 'ignore'>('');
  const [actionError, setActionError] = useState('');

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

  function openDetail(item: PendingRecordItem) {
    setSelected(item);
    setResolveRegNo(String(item.candidate_registry_no || '').trim());
    setIgnoreReason('');
    setActionError('');
    setDetailOpen(true);
  }

  async function resolveSelected() {
    if (!selected) return;
    const registrationNo = resolveRegNo.trim();
    if (!registrationNo) {
      setActionError('E_NO_REG_NO - registration_no is required');
      return;
    }
    setActionLoading('resolve');
    setActionError('');
    try {
      const res = await fetch(`/api/admin/pending/${encodeURIComponent(selected.id)}/resolve`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ registration_no: registrationNo }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok || Number((body as any)?.code) !== 0) {
        const msg = formatApiError(body, `HTTP ${res.status}`);
        setActionError(msg);
        toast({ variant: 'destructive', title: '解决失败', description: msg });
        return;
      }
      toast({ title: '解决成功', description: `pending_id=${selected.id}` });
      await refresh(offset);
      setDetailOpen(false);
    } catch (e) {
      const msg = String((e as Error)?.message || e || '网络错误');
      setActionError(msg);
      toast({ variant: 'destructive', title: '解决失败', description: msg });
    } finally {
      setActionLoading('');
    }
  }

  async function ignoreSelected() {
    if (!selected) return;
    setActionLoading('ignore');
    setActionError('');
    try {
      const res = await fetch(`/api/admin/pending/${encodeURIComponent(selected.id)}/ignore`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ reason: ignoreReason.trim() || null }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok || Number((body as any)?.code) !== 0) {
        const msg = formatApiError(body, `HTTP ${res.status}`);
        setActionError(msg);
        toast({ variant: 'destructive', title: '忽略失败', description: msg });
        return;
      }
      toast({ title: '忽略成功', description: `pending_id=${selected.id}` });
      await refresh(offset);
      setDetailOpen(false);
    } catch (e) {
      const msg = String((e as Error)?.message || e || '网络错误');
      setActionError(msg);
      toast({ variant: 'destructive', title: '忽略失败', description: msg });
    } finally {
      setActionLoading('');
    }
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
          <CardTitle>待处理统计</CardTitle>
          <CardDescription>基于 `/api/admin/pending/stats` 的 backlog/source/reason 聚合。</CardDescription>
        </CardHeader>
        <CardContent style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
          <Badge variant="muted">待处理总数: {Number(stats?.backlog?.open_total || 0)}</Badge>
          <Badge variant="muted">24h 已处理: {Number(stats?.backlog?.resolved_last_24h || 0)}</Badge>
          <Badge variant="muted">7d 已处理: {Number(stats?.backlog?.resolved_last_7d || 0)}</Badge>
          <Button onClick={() => void refresh()} disabled={loading}>
            {loading ? '刷新中...' : '刷新统计+列表'}
          </Button>
        </CardContent>
        <CardContent style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
          <div style={{ minWidth: 360, flex: 1 }}>
            <div className="muted" style={{ marginBottom: 6 }}>
              按来源统计
            </div>
            {(stats?.by_source_key || []).slice(0, 8).map((x) => (
              <div key={x.source_key} style={{ fontSize: 13, marginBottom: 4 }}>
                <b>{x.source_key}</b> · 待处理 {x.open} / 已解决 {x.resolved} / 已忽略 {x.ignored}
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
              按原因码统计（待处理）
            </div>
            {(stats?.by_reason_code || []).slice(0, 8).map((x) => (
              <div key={x.reason_code} style={{ fontSize: 13, marginBottom: 4 }}>
                <b>{x.reason_code || '（空）'}</b> · {x.open}
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>待处理列表</CardTitle>
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
            <option value="open">{ADMIN_PENDING_STATUS_ZH.open}</option>
            <option value="resolved">{ADMIN_PENDING_STATUS_ZH.resolved}</option>
            <option value="ignored">{ADMIN_PENDING_STATUS_ZH.ignored}</option>
            <option value="pending">{ADMIN_PENDING_STATUS_ZH.pending}</option>
            <option value="all">{ADMIN_PENDING_STATUS_ZH.all}</option>
          </Select>
          <Input
            placeholder="来源（可选，如 NMPA_REG / UDI_DI）"
            value={sourceKey}
            onChange={(e) => {
              setSourceKey(e.target.value);
              setOffset(0);
            }}
            style={{ minWidth: 220 }}
          />
          <Input
            placeholder="原因码（可选，如 E_NO_REG_NO）"
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
                    <th>来源</th>
                    <th>原因码</th>
                    <th>状态</th>
                    <th>候选信息</th>
                    <th>created_at</th>
                    <th>操作</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((it) => (
                    <tr key={it.id} onClick={() => openDetail(it)} style={{ cursor: 'pointer' }}>
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
                        <Badge variant={statusBadgeVariant(it.status)} title={it.status}>
                          {ADMIN_PENDING_STATUS_ZH[it.status as keyof typeof ADMIN_PENDING_STATUS_ZH] || it.status}
                        </Badge>
                      </td>
                      <td>
                        <div>{it.candidate_product_name || '-'}</div>
                        <div className="muted" style={{ fontSize: 12 }}>{it.candidate_company || '-'}</div>
                        <div className="muted" style={{ fontSize: 12 }}>{it.candidate_registry_no || '-'}</div>
                      </td>
                      <td>{it.created_at || '-'}</td>
                      <td>
                        <Button size="sm" variant="secondary" onClick={(e) => {
                          e.stopPropagation();
                          openDetail(it);
                        }}>
                          查看详情
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            </TableWrap>
          )}
        </CardContent>
      </Card>

      <Modal
        open={detailOpen}
        title="待处理详情"
        onClose={() => setDetailOpen(false)}
        footer={
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <Button
              variant="secondary"
              onClick={() => void ignoreSelected()}
              disabled={actionLoading !== ''}
            >
              {actionLoading === 'ignore' ? '忽略中...' : '忽略'}
            </Button>
            <Button
              onClick={() => void resolveSelected()}
              disabled={actionLoading !== ''}
            >
              {actionLoading === 'resolve' ? '处理中...' : '解决'}
            </Button>
          </div>
        }
      >
        {!selected ? (
          <div className="muted">未选择记录</div>
        ) : (
          <div className="grid" style={{ gap: 10 }}>
            {actionError ? (
              <div className="card" style={{ border: '1px solid var(--danger)', color: 'var(--danger)' }}>
                {actionError}
              </div>
            ) : null}
              <div className="columns-2">
              <div>
                <div className="muted">来源（source_key）</div>
                <div>{selected.source_key}</div>
              </div>
              <div>
                <div className="muted">原因码（reason_code）</div>
                <div>{selected.reason_code}</div>
              </div>
              <div>
                <div className="muted">created_at</div>
                <div>{selected.created_at || '-'}</div>
              </div>
              <div>
                <div className="muted">原始文档 raw_document_id</div>
                <div style={{ wordBreak: 'break-all' }}>{selected.raw_document_id || '-'}</div>
              </div>
              <div>
                <div className="muted">候选产品名 candidate_product_name</div>
                <div>{selected.candidate_product_name || '-'}</div>
              </div>
              <div>
                <div className="muted">候选企业 candidate_company</div>
                <div>{selected.candidate_company || '-'}</div>
              </div>
              <div>
                <div className="muted">候选注册证号 candidate_registry_no</div>
                <div>{selected.candidate_registry_no || '-'}</div>
              </div>
              <div>
                <div className="muted">状态 status</div>
                <div>{selected.status}</div>
              </div>
            </div>
            <div>
              <div className="muted" style={{ marginBottom: 4 }}>解决：注册证号（registration_no）</div>
              <Input
                value={resolveRegNo}
                onChange={(e) => setResolveRegNo(e.target.value)}
                placeholder="输入注册证号（如：国械注准2020XXXX 或 粤械注准2014XXXX）"
              />
              <div className="muted" style={{ marginTop: 6 }}>
                只填注册证号即可；系统会归一化并按 canonical key 写入 registrations，然后补齐关联。
              </div>
            </div>
            <div>
              <div className="muted" style={{ marginBottom: 4 }}>忽略：原因（可选）</div>
              <Textarea
                value={ignoreReason}
                onChange={(e) => setIgnoreReason(e.target.value)}
                placeholder="忽略原因（可选）"
              />
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
