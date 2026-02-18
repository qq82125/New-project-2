'use client';

import Link from 'next/link';
import { useEffect, useMemo, useState } from 'react';

import { Badge } from '../ui/badge';
import { Button } from '../ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card';
import { toast } from '../ui/use-toast';
import { refreshAuth, useAuth } from '../auth/use-auth';
import { PRO_COPY, PRO_TRIAL_HREF } from '../../constants/pro';
import { PLAN_STATUS_ZH, PLAN_ZH, ROLE_ZH, labelFrom } from '../../constants/display';

type MeData = {
  id?: number;
  email?: string;
  role?: string;
  created_at?: string | null;
  plan?: string;
  plan_status?: string;
  plan_expires_at?: string | null;
  is_pro?: boolean;
  is_admin?: boolean;
};

type ContactInfo = { email?: string | null; wecom?: string | null; form_url?: string | null };
type ContactInfoResp = { code: number; message: string; data: ContactInfo };

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
  const [contact, setContact] = useState<ContactInfo | null>(null);

  useEffect(() => {
    // Best-effort load (public endpoint). Keep existing hardcoded fallbacks if it fails.
    fetch('/api/public/contact-info', { cache: 'no-store' })
      .then((r) => (r.ok ? r.json() : null))
      .then((body: ContactInfoResp | null) => {
        if (!body || body.code !== 0) return;
        setContact(body.data || null);
      })
      .catch(() => null);
  }, []);

  useEffect(() => {
    // Keep in sync with global auth store when available.
    if (!auth.loading && auth.user) {
      setMe((prev) => {
        const keep: Partial<MeData> = {};
        if (prev && prev.plan !== undefined) keep.plan = prev.plan;
        if (prev && prev.plan_status !== undefined) keep.plan_status = prev.plan_status;
        if (prev && prev.plan_expires_at !== undefined) keep.plan_expires_at = prev.plan_expires_at;
        if (prev && prev.is_pro !== undefined) keep.is_pro = prev.is_pro;
        if (prev && prev.is_admin !== undefined) keep.is_admin = prev.is_admin;
        return {
          ...(prev || {}),
          ...auth.user,
          ...keep,
        };
      });
    }
  }, [auth.loading, auth.user]);

  const planStatus = (me?.plan_status || 'inactive').toLowerCase();
  const isPro = Boolean(me?.is_pro || me?.is_admin || (me?.plan || '').toLowerCase().includes('pro'));
  const planLabel = isPro ? labelFrom(PLAN_ZH, 'pro') : labelFrom(PLAN_ZH, 'free');
  const expiresAt = me?.plan_expires_at || null;
  const remainingDays = useMemo(() => {
    if (!expiresAt) return null;
    const d = new Date(expiresAt);
    if (!Number.isFinite(d.getTime())) return null;
    const diff = d.getTime() - Date.now();
    return Math.floor(diff / 86400000);
  }, [expiresAt]);

  const isPlanActive = useMemo(() => {
    if (!isPro) return false;
    const s = (planStatus || '').toLowerCase();
    if (s !== 'active' && s !== 'trial') return false;
    // If no expiry is configured, treat as active but "expires unknown".
    if (remainingDays === null) return true;
    return remainingDays >= 0;
  }, [isPro, planStatus, remainingDays]);

  const isExpired = useMemo(() => remainingDays !== null && remainingDays < 0, [remainingDays]);
  const isExpiringSoon = useMemo(
    () => isPlanActive && remainingDays !== null && remainingDays >= 0 && remainingDays < 30,
    [isPlanActive, remainingDays]
  );

  async function refreshMe() {
    setLoading(true);
    try {
      const [authRes, planRes] = await Promise.all([
        fetch(`/api/auth/me`, { method: 'GET', credentials: 'include', cache: 'no-store' }),
        fetch(`/api/me`, { method: 'GET', credentials: 'include', cache: 'no-store' }),
      ]);

      if (authRes.status === 401 || planRes.status === 401) {
        window.location.href = '/login';
        return;
      }
      if (!authRes.ok) {
        toast({ variant: 'destructive', title: '加载失败', description: `auth/me (${authRes.status})` });
        return;
      }

      const authBody = await authRes.json().catch(() => ({}));
      const planBody = await planRes.json().catch(() => ({}));
      const base = authBody?.data || null;
      const plan0 = planBody?.data?.plan || null;
      setMe(
        base
          ? {
              ...base,
              plan: plan0?.plan ?? base.plan,
              plan_status: plan0?.plan_status ?? base.plan_status,
              plan_expires_at: plan0?.plan_expires_at ?? base.plan_expires_at,
              is_pro: plan0?.is_pro ?? base.is_pro,
              is_admin: plan0?.is_admin ?? base.is_admin,
            }
          : null
      );
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
        邮箱：<span style={{ color: 'var(--ink)' }}>{contact?.email || 'sales@example.com'}</span>
      </div>
      <div className="muted">企业微信：{contact?.wecom || '（占位）扫码/ID'}</div>
      <div className="muted">表单：{contact?.form_url || 'https://example.com/form'}</div>
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
              <Badge variant={me?.role === 'admin' ? 'success' : 'muted'}>{labelFrom(ROLE_ZH, me?.role)}</Badge>
            </div>
            <div className="muted">注册时间：{me?.created_at ? new Date(me.created_at).toLocaleString() : '-'}</div>
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
              <Button variant="secondary" type="button" onClick={refreshMe} disabled={loading}>
                刷新状态
              </Button>
              <Button variant="ghost" type="button" onClick={() => (window.location.href = '/')} disabled={loading}>
                返回仪表盘
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
            {!isPro ? (
              <>
                <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
                  <Badge variant="muted">当前计划：{planLabel}</Badge>
                  <Badge variant={statusBadgeVariant(planStatus)}>{labelFrom(PLAN_STATUS_ZH, planStatus)}</Badge>
                </div>
                <div className="muted">到期日：以订阅为准/待配置</div>
                <div className="muted">权益简述：</div>
                <div className="muted">· 可浏览仪表盘</div>
                <div className="muted">· 不含行业周报</div>
                <div className="muted">· 订阅数量有限</div>
                <div className="grid" style={{ gap: 6 }}>
                  <Button type="button" onClick={() => (window.location.href = PRO_TRIAL_HREF)} disabled={loading}>
                    {PRO_COPY.banner.free_cta}
                  </Button>
                  <div className="muted">请联系管理员或通过对公方式开通</div>
                  {contactInfo}
                </div>
              </>
            ) : isPlanActive ? (
              <>
                <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
                  <Badge variant="muted">当前计划：{planLabel}</Badge>
                  <Badge variant={isExpiringSoon ? 'danger' : 'success'}>{isExpiringSoon ? '即将到期' : '正常'}</Badge>
                </div>
                <div className="muted">会员状态：{labelFrom(PLAN_STATUS_ZH, planStatus)}</div>
                <div className="muted">到期日：{expiresAt ? fmtDate(expiresAt) : '以订阅为准/待配置'}</div>
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
                  <Badge variant="muted">当前计划：{planLabel}</Badge>
                  <Badge variant="danger">{planStatus === 'suspended' ? '已暂停' : '已过期/不可用'}</Badge>
                </div>
                <div className="muted">会员状态：{labelFrom(PLAN_STATUS_ZH, planStatus)}</div>
                <div className="muted">到期日：{expiresAt ? fmtDate(expiresAt) : '以订阅为准/待配置'}</div>
                {remainingDays !== null ? <div className="muted">剩余天数：{`${remainingDays} 天`}</div> : null}
                <div className="grid" style={{ gap: 6 }}>
                  <Button type="button" onClick={() => (window.location.href = '/contact?intent=pro')} disabled={loading}>
                    联系恢复专业版
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
