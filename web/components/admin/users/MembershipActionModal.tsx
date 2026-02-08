'use client';

import { useMemo, useState } from 'react';

import { Button } from '../../ui/button';
import { Input } from '../../ui/input';
import { Textarea } from '../../ui/textarea';
import { Badge } from '../../ui/badge';
import { toast } from '../../ui/use-toast';
import { Modal } from '../../ui/modal';

import type { AdminUserItem, ApiResp } from './types';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

export type ActionType = 'grant' | 'extend' | 'suspend' | 'revoke';

function actionTitle(type: ActionType) {
  if (type === 'grant') return '开通年度会员';
  if (type === 'extend') return '续费（延长）';
  if (type === 'suspend') return '暂停会员';
  return '撤销会员';
}

export default function MembershipActionModal({
  open,
  type,
  user,
  onClose,
  onSuccess,
}: {
  open: boolean;
  type: ActionType;
  user: AdminUserItem | null;
  onClose: () => void;
  onSuccess: (next: AdminUserItem) => void;
}) {
  const [loading, setLoading] = useState(false);
  const [months, setMonths] = useState(12);
  const [reason, setReason] = useState('');
  const [note, setNote] = useState('');

  const canMonths = type === 'grant' || type === 'extend';
  const endpoint = useMemo(() => {
    if (type === 'grant') return '/api/admin/membership/grant';
    if (type === 'extend') return '/api/admin/membership/extend';
    if (type === 'suspend') return '/api/admin/membership/suspend';
    return '/api/admin/membership/revoke';
  }, [type]);

  async function submit() {
    if (!user) return;
    if (canMonths && (!Number.isFinite(months) || months <= 0)) {
      toast({ variant: 'destructive', title: '参数错误', description: 'months 必须 > 0' });
      return;
    }

    setLoading(true);
    try {
      const body: any = { user_id: user.id, reason: reason.trim() || null, note: note.trim() || null };
      if (type === 'grant') body.plan = 'pro_annual';
      if (canMonths) body.months = months;

      const res = await fetch(`${API_BASE}${endpoint}`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const text = await res.text();
      let parsedAny: any = null;
      try {
        parsedAny = JSON.parse(text);
      } catch {
        parsedAny = null;
      }

      // Debug prints for grant/extend failures (no sensitive fields in payload).
      // eslint-disable-next-line no-console
      console.debug('[admin-membership]', {
        endpoint,
        status: res.status,
        payload: body,
        response_body: parsedAny ?? text,
      });

      if (!res.ok) {
        // FastAPI validation error: {detail:[{loc,msg,type}...]}
        if (res.status === 422 && parsedAny && Array.isArray(parsedAny.detail)) {
          const msg = parsedAny.detail
            .map((d: any) => {
              const loc = Array.isArray(d.loc) ? d.loc.filter((x: any) => x !== 'body').join('.') : 'body';
              const m = d.msg || 'invalid';
              return `${loc}: ${m}`;
            })
            .join('\n');
          toast({ variant: 'destructive', title: '参数校验失败', description: msg });
          return;
        }
        const detail = parsedAny?.detail;
        const msg = (typeof detail === 'string' && detail) || parsedAny?.message || `操作失败 (${res.status})`;
        toast({ variant: 'destructive', title: '操作失败', description: msg });
        return;
      }
      const parsed = parsedAny as ApiResp<AdminUserItem> | null;
      if (!parsed || parsed.code !== 0) {
        const msg = parsed?.message || '接口返回异常';
        toast({ variant: 'destructive', title: '操作失败', description: msg });
        return;
      }

      onSuccess(parsed.data);
      toast({
        title: '操作成功',
        description: `${parsed.data.email} -> ${parsed.data.plan}/${parsed.data.plan_status}`,
      });
      setReason('');
      setNote('');
      setMonths(12);
      onClose();
    } catch (e) {
      const msg = e instanceof Error ? e.message : '网络错误';
      toast({ variant: 'destructive', title: '网络错误', description: msg });
    } finally {
      setLoading(false);
    }
  }

  return (
    <Modal
      open={open}
      title={actionTitle(type)}
      onClose={() => {
        if (loading) return;
        onClose();
      }}
      footer={
        <>
          <Button variant="secondary" type="button" onClick={onClose} disabled={loading}>
            取消
          </Button>
          <Button type="button" onClick={submit} disabled={loading || !user}>
            确认
          </Button>
        </>
      }
    >
      {!user ? (
        <div className="muted">未选择用户</div>
      ) : (
        <div className="grid" style={{ gap: 10 }}>
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
            <Badge variant="muted">#{user.id}</Badge>
            <Badge variant="muted">{user.email}</Badge>
            <Badge variant="muted">
              {user.plan}/{user.plan_status}
            </Badge>
          </div>

          {canMonths ? (
            <div className="grid" style={{ gap: 6 }}>
              <div className="muted">月份（months）</div>
              <Input
                type="number"
                min={1}
                value={months}
                onChange={(e) => setMonths(Number(e.target.value))}
                disabled={loading}
              />
              <div className="muted">建议：默认 12 个月</div>
            </div>
          ) : null}

          <div className="grid" style={{ gap: 6 }}>
            <div className="muted">原因（reason，可选）</div>
            <Textarea
              rows={3}
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              disabled={loading}
              placeholder="例如：合同号/收款编号/赠送原因"
              style={{ minHeight: 90 }}
            />
          </div>

          <div className="grid" style={{ gap: 6 }}>
            <div className="muted">备注（note，可选）</div>
            <Textarea
              rows={3}
              value={note}
              onChange={(e) => setNote(e.target.value)}
              disabled={loading}
              placeholder="内部备注"
              style={{ minHeight: 90 }}
            />
          </div>
        </div>
      )}
    </Modal>
  );
}
