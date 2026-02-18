'use client';

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

type PendingDocItem = {
  id: string;
  raw_document_id: string;
  source_run_id?: number | null;
  reason_code: string;
  status: string;
  created_at?: string | null;
  updated_at?: string | null;
};

type PendingDocListResp = {
  code: number;
  message: string;
  data?: {
    items: PendingDocItem[];
    count: number;
    total?: number;
    limit?: number;
    offset?: number;
    order_by?: string;
    status?: string;
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
  if (typeof detail === 'string' && detail.trim()) return [code, message, detail].filter(Boolean).join(' - ');
  if (code || message) return [code, message].filter(Boolean).join(' - ');
  return unknownError;
}

function statusBadgeVariant(status: string): 'muted' | 'success' | 'warning' | 'danger' {
  const s = String(status || '').toLowerCase();
  if (s === 'pending') return 'warning';
  if (s === 'resolved') return 'success';
  if (s === 'ignored') return 'muted';
  return 'danger';
}

export default function PendingDocumentsManager({
  initialItems,
  initialTotal,
}: {
  initialItems: PendingDocItem[];
  initialTotal: number;
}) {
  const [items, setItems] = useState<PendingDocItem[]>(initialItems || []);
  const [total, setTotal] = useState<number>(initialTotal || 0);
  const [status, setStatus] = useState<string>('pending');
  const [query, setQuery] = useState<string>('');
  const [offset, setOffset] = useState<number>(0);
  const [loading, setLoading] = useState(false);

  const [detailOpen, setDetailOpen] = useState(false);
  const [selected, setSelected] = useState<PendingDocItem | null>(null);
  const [resolveRegNo, setResolveRegNo] = useState('');
  const [resolveProductName, setResolveProductName] = useState('');
  const [ignoreReason, setIgnoreReason] = useState('');
  const [actionLoading, setActionLoading] = useState<'' | 'resolve' | 'ignore'>('');
  const [actionError, setActionError] = useState('');

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return items;
    return items.filter((x) => {
      return (
        (x.reason_code || '').toLowerCase().includes(q) ||
        (x.raw_document_id || '').toLowerCase().includes(q) ||
        String(x.source_run_id || '').toLowerCase().includes(q)
      );
    });
  }, [items, query]);

  function openDetail(item: PendingDocItem) {
    setSelected(item);
    setResolveRegNo('');
    setResolveProductName('');
    setIgnoreReason('');
    setActionError('');
    setDetailOpen(true);
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

      const res = await fetch(`/api/admin/pending-documents?${params.toString()}`, {
        credentials: 'include',
        cache: 'no-store',
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok || Number((body as any)?.code) !== 0) {
        throw new Error(formatApiError(body, `HTTP ${res.status}`));
      }
      const data = (body as PendingDocListResp).data;
      setItems(data?.items || []);
      setTotal(Number(data?.total ?? data?.count ?? 0));
      setOffset(useOffset);
    } catch (e) {
      toast({ variant: 'destructive', title: '刷新失败', description: String((e as Error)?.message || e) });
    } finally {
      setLoading(false);
    }
  }

  async function resolveSelected() {
    if (!selected) return;
    const registrationNo = resolveRegNo.trim();
    if (!registrationNo) {
      setActionError('E_CANONICAL_KEY_MISSING - registration_no is required');
      return;
    }
    setActionLoading('resolve');
    setActionError('');
    try {
      const res = await fetch(`/api/admin/pending-documents/${encodeURIComponent(selected.id)}/resolve`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ registration_no: registrationNo, product_name: resolveProductName.trim() || null }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok || Number((body as any)?.code) !== 0) {
        const msg = formatApiError(body, `HTTP ${res.status}`);
        setActionError(msg);
        toast({ variant: 'destructive', title: '解决失败', description: msg });
        return;
      }
      toast({ title: '解决成功', description: `pending_document_id=${selected.id}` });
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
      const res = await fetch(`/api/admin/pending-documents/${encodeURIComponent(selected.id)}/ignore`, {
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
      toast({ title: '已忽略', description: `pending_document_id=${selected.id}` });
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

  return (
    <div className="grid">
      <Card>
        <CardHeader>
          <CardTitle>队列筛选</CardTitle>
          <CardDescription>待处理文档队列只存“文档级积压”，用于手工补齐注册证号并重放入库。</CardDescription>
        </CardHeader>
        <CardContent style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
          <Select
            value={status}
            onChange={(e) => setStatus(String((e.target as HTMLSelectElement).value || 'pending'))}
            aria-label="status"
          >
            <option value="pending">待处理</option>
            <option value="resolved">已解决</option>
            <option value="ignored">已忽略</option>
            <option value="all">全部</option>
          </Select>
          <Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="搜索：原因码 / raw_document_id / source_run_id" />
          <Badge variant="muted">总计: {total}</Badge>
          <Button onClick={() => void refresh(0)} disabled={loading}>
            {loading ? '刷新中...' : '刷新'}
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>待处理文档列表</CardTitle>
          <CardDescription>点击行查看详情并执行“解决/忽略”。</CardDescription>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="grid">
              <Skeleton style={{ height: 120 }} />
              <Skeleton style={{ height: 120 }} />
            </div>
          ) : filtered.length === 0 ? (
            <EmptyState text="暂无待处理文档（当前筛选条件下没有匹配项）。" />
          ) : (
            <TableWrap>
              <Table>
                <thead>
                  <tr>
                    <th>状态</th>
                    <th>原因</th>
                    <th>批次ID（source_run_id）</th>
                    <th>原始文档ID（raw_document_id）</th>
                    <th>创建时间</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((x) => (
                    <tr key={x.id} className="row-hover" onClick={() => openDetail(x)}>
                      <td>
                        <Badge variant={statusBadgeVariant(x.status)} title={String(x.status || '')}>
                          {x.status === 'pending'
                            ? '待处理'
                            : x.status === 'resolved'
                              ? '已解决'
                              : x.status === 'ignored'
                                ? '已忽略'
                                : String(x.status || '')}
                        </Badge>
                      </td>
                      <td>{x.reason_code}</td>
                      <td>{x.source_run_id ?? '-'}</td>
                      <td className="mono">{x.raw_document_id}</td>
                      <td className="mono">{x.created_at ? String(x.created_at) : '-'}</td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            </TableWrap>
          )}

          <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 12 }}>
            <Button onClick={() => void refresh(Math.max(0, offset - PAGE_SIZE))} disabled={loading || offset <= 0}>
              上一页
            </Button>
            <span className="muted">
              offset {offset} / total {total}
            </span>
            <Button
              onClick={() => void refresh(offset + PAGE_SIZE)}
              disabled={loading || offset + PAGE_SIZE >= total}
            >
              下一页
            </Button>
          </div>
        </CardContent>
      </Card>

      <Modal open={detailOpen} onClose={() => setDetailOpen(false)} title="待处理文档详情">
        {!selected ? null : (
          <div className="grid">
            <Card>
              <CardHeader>
                <CardTitle>基本信息</CardTitle>
                <CardDescription>用于定位证据与回放批次（不需要手动修改）。</CardDescription>
              </CardHeader>
              <CardContent className="grid">
                <div className="muted">记录 ID: <span className="mono">{selected.id}</span></div>
                <div className="muted">原始文档 raw_document_id: <span className="mono">{selected.raw_document_id}</span></div>
                <div className="muted">批次 source_run_id: <span className="mono">{String(selected.source_run_id ?? '-')}</span></div>
                <div className="muted">原因码 reason_code: <span className="mono">{selected.reason_code}</span></div>
                <div className="muted">状态 status: <span className="mono">{selected.status}</span></div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>解决（补齐注册证号并重放入库）</CardTitle>
                <CardDescription>会触发标准入库路径：先 registrations，再写衍生实体。</CardDescription>
              </CardHeader>
              <CardContent className="grid">
                <Input
                  value={resolveRegNo}
                  onChange={(e) => setResolveRegNo(e.target.value)}
                  placeholder="注册证号（必填，如：国械注准2020XXXX 或 粤械注准2014XXXX）"
                />
                <div className="muted" style={{ marginTop: -6 }}>
                  只填注册证号即可；系统会归一化并按 canonical key 写入 registrations。
                </div>
                <Input
                  value={resolveProductName}
                  onChange={(e) => setResolveProductName(e.target.value)}
                  placeholder="产品名称（可选，用于补齐展示）"
                />
                {actionError ? <div className="error">{actionError}</div> : null}
                <div style={{ display: 'flex', gap: 10 }}>
                  <Button onClick={() => void resolveSelected()} disabled={actionLoading === 'resolve'}>
                    {actionLoading === 'resolve' ? '处理中...' : '解决并入库'}
                  </Button>
                  <Button variant="secondary" onClick={() => void ignoreSelected()} disabled={actionLoading === 'ignore'}>
                    {actionLoading === 'ignore' ? '处理中...' : '忽略'}
                  </Button>
                </div>
                <Textarea value={ignoreReason} onChange={(e) => setIgnoreReason(e.target.value)} placeholder="忽略原因（可选）" />
              </CardContent>
            </Card>
          </div>
        )}
      </Modal>
    </div>
  );
}
