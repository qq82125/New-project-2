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
import { ADMIN_UDI_LINK_STATUS_ZH } from '../../constants/admin-i18n';

type PendingItem = {
  id: string;
  di: string;
  status: string;
  reason: string;
  reason_code?: string | null;
  match_reason?: string | null;
  confidence?: number;
  reversible?: boolean;
  linked_by?: string | null;
  candidate_company_name?: string | null;
  candidate_product_name?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

type ListResp = {
  code: number;
  message: string;
  data?: { items: PendingItem[]; count: number; status: string };
};

type BindResp = {
  code: number;
  message: string;
  data?: {
    pending_id: string;
    di: string;
    registration_no: string;
    match_type: string;
    confidence: number;
    status: string;
  };
};

const DEFAULT_LIMIT = 200;

export default function UdiPendingLinksManager({ initialItems }: { initialItems: PendingItem[] }) {
  const [items, setItems] = useState<PendingItem[]>(initialItems || []);
  const [status, setStatus] = useState<string>('PENDING');
  const [loading, setLoading] = useState(false);
  const [submittingId, setSubmittingId] = useState<string | null>(null);
  const [bindInputById, setBindInputById] = useState<Record<string, string>>({});
  const [query, setQuery] = useState('');
  const [lowConfidenceOnly, setLowConfidenceOnly] = useState(false);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return items;
    return items.filter((x) => {
      return (
        (x.di || '').toLowerCase().includes(q) ||
        (x.reason_code || '').toLowerCase().includes(q) ||
        (x.candidate_company_name || '').toLowerCase().includes(q) ||
        (x.candidate_product_name || '').toLowerCase().includes(q)
      );
    });
  }, [items, query]);

  async function refresh(nextStatus?: string, onlyLowConfidence?: boolean) {
    const st = (nextStatus || status || 'PENDING').toUpperCase();
    const lowConfidence = Boolean(onlyLowConfidence ?? lowConfidenceOnly);
    const confidenceQuery = lowConfidence ? '&confidence_lt=0.6' : '';
    setLoading(true);
    try {
      const res = await fetch(`/api/admin/udi/pending-links?status=${encodeURIComponent(st)}&limit=${DEFAULT_LIMIT}${confidenceQuery}`, {
        credentials: 'include',
        cache: 'no-store',
      });
      if (!res.ok) {
        const detail = await res.text();
        throw new Error(detail || `HTTP ${res.status}`);
      }
      const body = (await res.json()) as ListResp;
      if (body.code !== 0 || !body.data) throw new Error(body.message || '加载失败');
      setItems(body.data.items || []);
    } catch (e) {
      toast({ variant: 'destructive', title: '刷新失败', description: String((e as Error)?.message || e) });
    } finally {
      setLoading(false);
    }
  }

  async function bindOne(item: PendingItem) {
    const regNo = (bindInputById[item.id] || '').trim();
    if (!regNo) {
      toast({ variant: 'destructive', title: '缺少注册证号', description: `请先填写 ${item.di} 关联的注册证号（registration_no）` });
      return;
    }
    setSubmittingId(item.id);
    try {
      const res = await fetch(`/api/admin/udi/pending-links/${encodeURIComponent(item.id)}/bind`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ registration_no: regNo, confidence: 0.95 }),
      });
      const body = (await res.json()) as BindResp;
      if (!res.ok || body.code !== 0 || !body.data) {
        throw new Error(body.message || `HTTP ${res.status}`);
      }
      toast({
        title: '绑定成功',
        description: `DI ${body.data.di} -> ${body.data.registration_no} (${body.data.match_type})`,
      });
      setItems((prev) => prev.filter((x) => x.id !== item.id));
    } catch (e) {
      toast({ variant: 'destructive', title: '绑定失败', description: String((e as Error)?.message || e) });
    } finally {
      setSubmittingId(null);
    }
  }

  return (
    <div className="grid">
      <Card>
        <CardHeader>
          <CardTitle>UDI 待映射队列</CardTitle>
          <CardDescription>处理自动解析失败的 DI，手动绑定到注册证号后将写入 product_udi_map（manual）。</CardDescription>
        </CardHeader>
        <CardContent style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
          <Select
            value={status}
            onChange={(e) => {
              const next = String(e.target.value || 'PENDING').toUpperCase();
              setStatus(next);
              void refresh(next, lowConfidenceOnly);
            }}
            style={{ minWidth: 180 }}
          >
            <option value="PENDING">{ADMIN_UDI_LINK_STATUS_ZH.PENDING}</option>
            <option value="RETRYING">{ADMIN_UDI_LINK_STATUS_ZH.RETRYING}</option>
            <option value="RESOLVED">{ADMIN_UDI_LINK_STATUS_ZH.RESOLVED}</option>
            <option value="ALL">{ADMIN_UDI_LINK_STATUS_ZH.ALL}</option>
          </Select>
          <Input
            placeholder="按 UDI-DI / 候选公司 / 候选产品过滤"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            style={{ minWidth: 320 }}
          />
          <Button
            variant={lowConfidenceOnly ? 'default' : 'secondary'}
            onClick={() => {
              const next = !lowConfidenceOnly;
              setLowConfidenceOnly(next);
              void refresh(status, next);
            }}
          >
            低置信(&lt;0.6)
          </Button>
          <Button onClick={() => void refresh()} disabled={loading}>
            {loading ? '刷新中...' : '刷新'}
          </Button>
          <Badge variant="muted">显示: {filtered.length}</Badge>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>待处理列表</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <Skeleton style={{ height: 96 }} />
          ) : filtered.length === 0 ? (
            <EmptyState text="当前条件下没有待处理记录" />
          ) : (
            <TableWrap>
              <Table>
                <thead>
                  <tr>
                    <th>UDI-DI</th>
                    <th>状态</th>
                    <th>原因</th>
                    <th>置信度</th>
                    <th>候选信息</th>
                    <th>手动绑定注册证号</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((it) => (
                    <tr key={it.id}>
                      <td>{it.di}</td>
                      <td>
                        <Badge variant="muted" title={it.status}>
                          {ADMIN_UDI_LINK_STATUS_ZH[it.status as keyof typeof ADMIN_UDI_LINK_STATUS_ZH] || it.status}
                        </Badge>
                      </td>
                      <td>
                        <div>{it.reason_code || it.reason}</div>
                        <div className="muted" style={{ fontSize: 12 }}>{it.reason}</div>
                      </td>
                      <td>
                        <div>{typeof it.confidence === 'number' ? it.confidence.toFixed(2) : '-'}</div>
                        <div className="muted" style={{ fontSize: 12 }}>{it.match_reason || '-'}</div>
                      </td>
                      <td>
                        <div>{it.candidate_product_name || '-'}</div>
                        <div className="muted" style={{ fontSize: 12 }}>{it.candidate_company_name || '-'}</div>
                      </td>
                      <td>
                        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                          <Input
                            placeholder="如：国械注准2026xxxx（用于人工绑定）"
                            value={bindInputById[it.id] || ''}
                            onChange={(e) =>
                              setBindInputById((prev) => ({ ...prev, [it.id]: e.target.value }))
                            }
                            style={{ minWidth: 220 }}
                          />
                          <Button
                            onClick={() => void bindOne(it)}
                            disabled={submittingId === it.id || it.status === 'RESOLVED'}
                          >
                            {submittingId === it.id ? '提交中...' : '绑定'}
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
