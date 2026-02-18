'use client';

import Link from 'next/link';
import { useEffect, useMemo, useState } from 'react';

import { Badge } from '../../ui/badge';
import { Button } from '../../ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../ui/card';
import { Input } from '../../ui/input';
import { Skeleton } from '../../ui/skeleton';
import { Table, TableWrap } from '../../ui/table';
import { toast } from '../../ui/use-toast';
import { EmptyState, ErrorState } from '../../States';

import MembershipActionModal, { ActionType } from './MembershipActionModal';
import type { AdminUserItem, ApiResp } from './types';
import { PLAN_STATUS_ZH, PLAN_ZH, labelFrom } from '../../../constants/display';

function fmtTs(ts?: string | null) {
  if (!ts) return '-';
  try {
    return new Date(ts).toLocaleString();
  } catch {
    return ts;
  }
}

function statusVariant(status: string): 'success' | 'danger' | 'muted' {
  const s = (status || '').toLowerCase();
  if (s === 'active') return 'success';
  if (s === 'suspended') return 'danger';
  return 'muted';
}

export default function AdminUsersManager() {
  const [query, setQuery] = useState('');
  const [limit, setLimit] = useState(50);
  const [offset, setOffset] = useState(0);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [items, setItems] = useState<AdminUserItem[]>([]);

  const [modalOpen, setModalOpen] = useState(false);
  const [modalType, setModalType] = useState<ActionType>('grant');
  const [modalUser, setModalUser] = useState<AdminUserItem | null>(null);

  const queryKey = useMemo(
    () => `q=${encodeURIComponent(query.trim())}&limit=${limit}&offset=${offset}`,
    [query, limit, offset],
  );

  async function fetchUsers() {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/admin/users?query=${encodeURIComponent(query.trim())}&limit=${limit}&offset=${offset}`, {
        credentials: 'include',
        cache: 'no-store',
      });
      if (!res.ok) {
        setError(`加载失败 (${res.status})`);
        return;
      }
      const body = (await res.json()) as ApiResp<{ items: AdminUserItem[]; limit: number; offset: number }>;
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

  function openAction(type: ActionType, u: AdminUserItem) {
    setModalType(type);
    setModalUser(u);
    setModalOpen(true);
  }

  function updateRow(next: AdminUserItem) {
    setItems((prev) => prev.map((x) => (x.id === next.id ? next : x)));
  }

  useEffect(() => {
    void fetchUsers();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [queryKey]);

  return (
    <Card>
      <CardHeader>
        <CardTitle>用户列表</CardTitle>
        <CardDescription>按邮箱搜索，支持分页。操作后会实时刷新该用户行。</CardDescription>
      </CardHeader>
      <CardContent className="grid" style={{ gap: 12 }}>
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
          <Input
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setOffset(0);
            }}
            placeholder="搜索邮箱（支持模糊匹配）"
            style={{ minWidth: 320 }}
            disabled={loading}
          />

          <Input
            type="number"
            min={1}
            max={200}
            value={limit}
            onChange={(e) => setLimit(Math.max(1, Math.min(200, Number(e.target.value) || 50)))}
            disabled={loading}
            style={{ width: 110 }}
            title="limit"
          />

          <Button variant="secondary" onClick={fetchUsers} disabled={loading}>
            刷新
          </Button>

          <Badge variant="muted">/api/admin/users</Badge>
        </div>

        {error ? <ErrorState text={error} /> : null}

        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
          <Button
            variant="secondary"
            onClick={() => setOffset((v) => Math.max(0, v - limit))}
            disabled={loading || offset === 0}
          >
            上一页
          </Button>
          <Button variant="secondary" onClick={() => setOffset((v) => v + limit)} disabled={loading || items.length < limit}>
            下一页
          </Button>
          <span className="muted">
            起始偏移：{offset} · 每页数量：{limit}
          </span>
        </div>

        {loading && items.length === 0 ? (
          <div className="grid">
            <Skeleton height={28} />
            <Skeleton height={220} />
          </div>
        ) : items.length === 0 ? (
          <EmptyState text="暂无用户" />
        ) : (
          <TableWrap>
            <Table>
              <thead>
                <tr>
                  <th>邮箱</th>
                  <th style={{ width: 140 }}>会员计划</th>
                  <th style={{ width: 140 }}>会员状态</th>
                  <th style={{ width: 200 }}>到期时间</th>
                  <th style={{ width: 360 }}>操作</th>
                </tr>
              </thead>
              <tbody>
                {items.map((u) => (
                  <tr key={u.id}>
                    <td>
                      <div style={{ display: 'grid', gap: 4 }}>
                        <Link href={`/admin/users/${u.id}`}>{u.email}</Link>
                        <span className="muted">#{u.id} · 创建于 {fmtTs(u.created_at)}</span>
                      </div>
                    </td>
                    <td>
                      <Badge variant="muted">{labelFrom(PLAN_ZH, u.plan)}</Badge>
                    </td>
                    <td>
                      <Badge variant={statusVariant(u.plan_status)}>{labelFrom(PLAN_STATUS_ZH, u.plan_status)}</Badge>
                    </td>
                    <td className="muted">{fmtTs(u.plan_expires_at)}</td>
                    <td>
                      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                        <Button size="sm" onClick={() => openAction('grant', u)} disabled={loading}>
                          开通
                        </Button>
                        <Button size="sm" variant="secondary" onClick={() => openAction('extend', u)} disabled={loading}>
                          续费
                        </Button>
                        <Button size="sm" variant="secondary" onClick={() => openAction('suspend', u)} disabled={loading}>
                          暂停
                        </Button>
                        <Button size="sm" variant="destructive" onClick={() => openAction('revoke', u)} disabled={loading}>
                          撤销
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </Table>
          </TableWrap>
        )}

        <MembershipActionModal
          open={modalOpen}
          type={modalType}
          user={modalUser}
          onClose={() => setModalOpen(false)}
          onSuccess={(next) => {
            updateRow(next);
            // best-effort: refresh list so paging/search remains consistent
            void fetchUsers();
          }}
        />
      </CardContent>
    </Card>
  );
}
