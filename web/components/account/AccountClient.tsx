'use client';

import Link from 'next/link';
import { useEffect, useMemo, useState } from 'react';

import { Badge } from '../ui/badge';
import { Button } from '../ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card';
import { toast } from '../ui/use-toast';
import { refreshAuth, useAuth } from '../auth/use-auth';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

type MeData = {
  id?: number;
  email?: string;
  role?: string;
  created_at?: string | null;
  plan?: string;
  plan_status?: string;
  plan_expires_at?: string | null;
  plan_remaining_days?: number | null;
};

function fmtDate(ts?: string | null) {
  if (!ts) return '-';
  const d = new Date(ts);
  if (!Number.isFinite(d.getTime())) return ts;
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

function statusBadgeVariant(status: string): 'success' | 'danger' | 'muted' {
  const s = (status || '').toLowerCase();
  if (s === 'active') return 'success';
  if (s === 'suspended') return 'danger';
  return 'muted';
}

export default function AccountClient({ initialMe }: { initialMe: MeData | null }) {
  const auth = useAuth();
  const [me, setMe] = useState<MeData | null>(initialMe);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    // Keep in sync with global auth store when available.
    if (!auth.loading && auth.user) {
      setMe((prev) => ({
        ...(prev || {}),
        ...auth.user,
      }));
    }
  }, [auth.loading, auth.user]);

  const plan = (me?.plan || 'free').toLowerCase();
  const planStatus = (me?.plan_status || 'inactive').toLowerCase();
  const remainingDays = me?.plan_remaining_days ?? null;

  const isProActive = useMemo(() => plan === 'pro_annual' && planStatus === 'active' && (remainingDays === null || remainingDays >= 0), [
    plan,
    planStatus,
    remainingDays,
  ]);

  const isExpiringSoon = useMemo(() => isProActive && remainingDays !== null && remainingDays < 30, [isProActive, remainingDays]);
  const isExpired = useMemo(() => plan === 'pro_annual' && planStatus === 'active' && remainingDays !== null && remainingDays < 0, [
    plan,
    planStatus,
    remainingDays,
  ]);

  async function refreshMe() {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/auth/me`, { method: 'GET', credentials: 'include', cache: 'no-store' });
      if (!res.ok) {
        toast({ variant: 'destructive', title: '加载失败', description: `auth/me (${res.status})` });
        return;
      }
      const body = await res.json();
      setMe(body?.data || null);
      await refreshAuth();
      toast({ title: '已刷新', description: '已更新会员状态' });
    } catch (e) {
      const msg = e instanceof Error ? e.message : '网络错误';
      toast({ variant: 'destructive', title: '网络错误', description: msg });
    } finally {
      setLoading(false);
    }
  }

  const contactInfo = (
    <div className="grid" style={{ gap: 6 }}>
      <div className="muted">
        邮箱：<span style={{ color: 'var(--ink)' }}>sales@example.com</span>
      </div>
      <div className="muted">企业微信：（占位）扫码/ID</div>
      <div className="muted">表单：（占位）https://example.com/form</div>
      <div className="muted">
        也可前往 <Link href="/contact">/contact</Link>
      </div>
    </div>
  );

  return (
    <div className="grid">
      <Card>
        <CardHeader>
          <CardTitle>用户中心</CardTitle>
          <CardDescription>查看账号信息与会员状态（ToB 开通/续费）。</CardDescription>
        </CardHeader>
      </Card>

      <div className="columns-2">
        <Card>
          <CardHeader>
            <CardTitle>用户信息</CardTitle>
            <CardDescription>登录账号与注册时间。</CardDescription>
          </CardHeader>
          <CardContent className="grid" style={{ gap: 8 }}>
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
              <Badge variant="muted">{me?.email || '-'}</Badge>
              <Badge variant="muted">#{me?.id || '-'}</Badge>
              <Badge variant={me?.role === 'admin' ? 'success' : 'muted'}>{me?.role || '-'}</Badge>
            </div>
            <div className="muted">注册时间：{me?.created_at ? new Date(me.created_at).toLocaleString() : '-'}</div>
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
              <Button variant="secondary" type="button" onClick={refreshMe} disabled={loading}>
                刷新状态
              </Button>
              <Button variant="ghost" type="button" onClick={() => (window.location.href = '/')} disabled={loading}>
                返回 Dashboard
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>会员状态</CardTitle>
            <CardDescription>当前套餐与到期信息。</CardDescription>
          </CardHeader>
          <CardContent className="grid" style={{ gap: 10 }}>
            {plan === 'free' ? (
              <>
                <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
                  <Badge variant="muted">当前套餐：Free</Badge>
                  <Badge variant={statusBadgeVariant(planStatus)}>{planStatus}</Badge>
                </div>
                <div className="muted">权益简述：</div>
                <div className="muted">· 可浏览 Dashboard</div>
                <div className="muted">· 不含行业周报</div>
                <div className="muted">· 订阅数量有限</div>
                <div className="grid" style={{ gap: 6 }}>
                  <Button type="button" onClick={() => (window.location.href = '/contact?intent=pro')} disabled={loading}>
                    升级为 Pro 年度会员
                  </Button>
                  <div className="muted">请联系管理员或通过对公方式开通</div>
                  {contactInfo}
                </div>
              </>
            ) : plan === 'pro_annual' && planStatus === 'active' && !isExpired ? (
              <>
                <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
                  <Badge variant="muted">当前套餐：Pro 年度会员</Badge>
                  <Badge variant={isExpiringSoon ? 'danger' : 'success'}>{isExpiringSoon ? '即将到期' : '正常'}</Badge>
                </div>
                <div className="muted">到期日：{fmtDate(me?.plan_expires_at)}</div>
                <div className="muted">剩余天数：{remainingDays === null ? '-' : `${remainingDays} 天`}</div>
                {isExpiringSoon ? <div className="error" style={{ padding: 10, borderRadius: 12, border: '1px solid var(--border)' }}>到期不足 30 天，建议尽快联系续费。</div> : null}
                <div className="grid" style={{ gap: 6 }}>
                  <Button type="button" onClick={() => (window.location.href = '/contact?intent=pro')} disabled={loading}>
                    联系续费
                  </Button>
                  {contactInfo}
                </div>
              </>
            ) : (
              <>
                <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
                  <Badge variant="muted">{plan === 'pro_annual' ? '套餐：Pro 年度会员' : `套餐：${plan}`}</Badge>
                  <Badge variant="danger">{planStatus === 'suspended' ? '已暂停' : '已过期/不可用'}</Badge>
                </div>
                <div className="muted">到期日：{fmtDate(me?.plan_expires_at)}</div>
                {remainingDays !== null ? <div className="muted">剩余天数：{`${remainingDays} 天`}</div> : null}
                <div className="grid" style={{ gap: 6 }}>
                  <Button type="button" onClick={() => (window.location.href = '/contact?intent=pro')} disabled={loading}>
                    联系恢复 Pro 会员
                  </Button>
                  {contactInfo}
                </div>
              </>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
