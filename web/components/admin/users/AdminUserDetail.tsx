'use client';

import Link from 'next/link';
import { useEffect, useMemo, useState } from 'react';

import { Badge } from '../../ui/badge';
import { Button } from '../../ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../ui/card';
import { Skeleton } from '../../ui/skeleton';
import { Table, TableWrap } from '../../ui/table';
import { toast } from '../../ui/use-toast';
import { EmptyState, ErrorState } from '../../States';

import MembershipActionModal, { ActionType } from './MembershipActionModal';
import type { AdminMembershipGrant, AdminUserDetail as AdminUserDetailT, AdminUserItem, ApiResp } from './types';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

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

function remainingDays(expiresAt?: string | null) {
  if (!expiresAt) return null;
  const exp = new Date(expiresAt).getTime();
  if (!Number.isFinite(exp)) return null;
  const now = Date.now();
  const diff = exp - now;
  return Math.floor(diff / 86400000);
}

export default function AdminUserDetail({ userId }: { userId: number }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [detail, setDetail] = useState<AdminUserDetailT | null>(null);

  const [modalOpen, setModalOpen] = useState(false);
  const [modalType, setModalType] = useState<ActionType>('grant');

  const user = detail?.user || null;
  const grants = detail?.recent_grants || [];

  const leftDays = useMemo(() => remainingDays(user?.plan_expires_at), [user?.plan_expires_at]);

  async function fetchDetail() {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/admin/users/${userId}?grants_limit=50`, {
        credentials: 'include',
        cache: 'no-store',
      });
      if (res.status === 404) {
        setError('用户不存在');
        setDetail(null);
        return;
      }
      if (!res.ok) {
        setError(`加载失败 (${res.status})`);
        return;
      }
      const body = (await res.json()) as ApiResp<AdminUserDetailT>;
      if (body.code !== 0) {
        setError(body.message || '接口返回异常');
        return;
      }
      setDetail(body.data);
    } catch (e) {
      setError(e instanceof Error ? e.message : '网络错误');
    } finally {
      setLoading(false);
    }
  }

  function openAction(type: ActionType) {
    setModalType(type);
    setModalOpen(true);
  }

  useEffect(() => {
    void fetchDetail();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userId]);

  return (
    <div className="grid">
      {error ? <ErrorState text={error} /> : null}

      {loading && !detail ? (
        <div className="grid">
          <Skeleton height={120} />
          <Skeleton height={160} />
        </div>
      ) : !detail ? (
        <EmptyState text="暂无数据" />
      ) : (
        <>
          <div className="columns-2">
            <Card>
              <CardHeader>
                <CardTitle>用户信息</CardTitle>
                <CardDescription>基础信息与权限角色。</CardDescription>
              </CardHeader>
              <CardContent className="grid" style={{ gap: 8 }}>
                <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
                  <Badge variant="muted">#{user!.id}</Badge>
                  <Badge variant="muted">{user!.email}</Badge>
                  <Badge variant={user!.role === 'admin' ? 'success' : 'muted'}>{user!.role}</Badge>
                </div>
                <div className="muted">创建时间：{fmtTs(user!.created_at)}</div>
                <div className="muted">
                  <Link href="/admin/users">返回列表</Link>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>会员状态</CardTitle>
                <CardDescription>plan/状态/到期日与剩余天数。</CardDescription>
              </CardHeader>
              <CardContent className="grid" style={{ gap: 10 }}>
                <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
                  <Badge variant="muted">{user!.plan}</Badge>
                  <Badge variant={statusVariant(user!.plan_status)}>{user!.plan_status}</Badge>
                  <Badge variant="muted">expires: {fmtTs(user!.plan_expires_at)}</Badge>
                </div>
                <div className="muted">
                  剩余天数：
                  {leftDays === null ? ' -' : leftDays >= 0 ? ` ${leftDays} 天` : ` 已过期 (${Math.abs(leftDays)} 天前)`}
                </div>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  <Button size="sm" onClick={() => openAction('grant')} disabled={loading}>
                    开通
                  </Button>
                  <Button size="sm" variant="secondary" onClick={() => openAction('extend')} disabled={loading}>
                    续费
                  </Button>
                  <Button size="sm" variant="secondary" onClick={() => openAction('suspend')} disabled={loading}>
                    暂停
                  </Button>
                  <Button size="sm" variant="destructive" onClick={() => openAction('revoke')} disabled={loading}>
                    撤销
                  </Button>
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={() => {
                      toast({ title: '已刷新', description: '已重新拉取用户与流水' });
                      void fetchDetail();
                    }}
                    disabled={loading}
                  >
                    刷新
                  </Button>
                </div>
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Grant 历史</CardTitle>
              <CardDescription>展示最近 50 条 membership_grants（start/end/reason/note）。</CardDescription>
            </CardHeader>
            <CardContent>
              {grants.length === 0 ? (
                <EmptyState text="暂无 grant 记录" />
              ) : (
                <TableWrap>
                  <Table>
                    <thead>
                      <tr>
                        <th style={{ width: 140 }}>Start</th>
                        <th style={{ width: 140 }}>End</th>
                        <th style={{ width: 120 }}>Plan</th>
                        <th style={{ width: 160 }}>Created</th>
                        <th>Reason</th>
                        <th>Note</th>
                      </tr>
                    </thead>
                    <tbody>
                      {grants.map((g: AdminMembershipGrant) => (
                        <tr key={g.id}>
                          <td className="muted">{fmtTs(g.start_at)}</td>
                          <td className="muted">{fmtTs(g.end_at)}</td>
                          <td>
                            <Badge variant="muted">{g.plan}</Badge>
                          </td>
                          <td className="muted">{fmtTs(g.created_at)}</td>
                          <td className="muted" style={{ maxWidth: 320 }}>
                            {g.reason || '-'}
                          </td>
                          <td className="muted" style={{ maxWidth: 320 }}>
                            {g.note || '-'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </Table>
                </TableWrap>
              )}
            </CardContent>
          </Card>

          <MembershipActionModal
            open={modalOpen}
            type={modalType}
            user={user as AdminUserItem}
            onClose={() => setModalOpen(false)}
            onSuccess={() => {
              // API returns updated user; but detail also contains grants so just refetch.
              void fetchDetail();
            }}
          />
        </>
      )}
    </div>
  );
}

