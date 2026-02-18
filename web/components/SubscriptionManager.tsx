'use client';

import { useMemo, useState } from 'react';
import Link from 'next/link';
import { toast } from './ui/use-toast';
import { useAuth } from './auth/use-auth';
import { PRO_SALES_HREF } from '../constants/pro';
import { fetchWithProHandling } from '../lib/fetch-client';

type Subscription = {
  id: number;
  subscriber_key?: string;
  channel?: string;
  email_to?: string | null;
  subscription_type: string;
  target_value: string;
  webhook_url?: string | null;
  is_active: boolean;
  last_digest_date?: string | null;
  created_at?: string;
};

type ApiEnvelope<T> = { code: number; message: string; data: T };

export function SubscriptionManager({
  initialType,
  initialTarget,
  initialSubs,
}: {
  initialType?: string;
  initialTarget?: string;
  initialSubs: Subscription[];
}) {
  const auth = useAuth();
  const [subs, setSubs] = useState<Subscription[]>(initialSubs);
  const [type, setType] = useState(initialType || 'company');
  const [target, setTarget] = useState(initialTarget || '');
  const [webhookUrl, setWebhookUrl] = useState('');
  const [loading, setLoading] = useState(false);

  const activeCount = useMemo(() => subs.filter((s) => s.is_active).length, [subs]);
  const quota = auth.user?.entitlements?.max_subscriptions;
  const plan = (auth.user?.plan || 'free').toLowerCase();

  async function createSub() {
    if (!target.trim()) return;
    setLoading(true);
    const res = await fetchWithProHandling(`/api/subscriptions`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({
        subscription_type: type,
        target_value: target,
        channel: 'webhook',
        webhook_url: webhookUrl || null,
      }),
    });
    setLoading(false);
    const bodyText = await res.text();
    let body: any = null;
    try {
      body = JSON.parse(bodyText);
    } catch {
      body = null;
    }

      if (!res.ok) {
        if (body?.error === 'SUBSCRIPTION_LIMIT') {
          toast({
            variant: 'destructive',
            title: '订阅数量达到上限',
            description: body?.message || '请升级专业版或联系开通。',
          });
          return;
        }
      toast({ variant: 'destructive', title: '创建失败', description: `请求失败 (${res.status})` });
      return;
    }

    const env = body as ApiEnvelope<Subscription>;
    if (!env || env.code !== 0) {
      toast({ variant: 'destructive', title: '创建失败', description: env?.message || '接口返回异常' });
      return;
    }
    setSubs([env.data, ...subs]);
  }

  async function deactivate(id: number) {
    toast({
      variant: 'destructive',
      title: '暂不支持',
      description: '当前版本未实现订阅停用 API。',
    });
  }

  return (
    <div className="grid">
      <div className="card">
        <h2>创建订阅</h2>
        <div className="controls">
          <select value={type} onChange={(e) => setType(e.target.value)}>
            <option value="company">企业</option>
            <option value="registration">证照</option>
            <option value="keyword">关键词</option>
          </select>
          <input value={target} onChange={(e) => setTarget(e.target.value)} placeholder="订阅目标（如企业名/注册证号/关键词）" />
          <input value={webhookUrl} onChange={(e) => setWebhookUrl(e.target.value)} placeholder="回调地址（Webhook，可选，用于接收推送）" />
          <button onClick={createSub} disabled={loading}>
            {loading ? '提交中...' : '订阅'}
          </button>
        </div>
      </div>

      <div className="card">
        活跃订阅：{activeCount}
        {quota ? (
          <>
            {' '}
            · 配额：{activeCount}/{quota}（{plan === 'pro_annual' ? '专业版（年度）' : '免费版'}）
          </>
        ) : null}
        {' '}
        · <Link href={PRO_SALES_HREF}>联系开通/试用</Link>
      </div>

      {subs.map((sub) => (
        <div className="card" key={sub.id}>
          <h3>
            #{sub.id} {sub.subscription_type} / {sub.target_value}
          </h3>
          <p>状态: {sub.is_active ? '启用' : '未启用'}</p>
          <p>最近汇总: {sub.last_digest_date || '-'}</p>
          <p>回调地址: {sub.webhook_url || '-'}</p>
          {sub.is_active && <button onClick={() => deactivate(sub.id)}>停用</button>}
        </div>
      ))}
    </div>
  );
}
