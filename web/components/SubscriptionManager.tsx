'use client';

import { useMemo, useState } from 'react';

const API = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

type Subscription = {
  id: number;
  subscription_type: string;
  target_value: string;
  webhook_url?: string | null;
  is_active: boolean;
  last_digest_date?: string | null;
};

export function SubscriptionManager({
  initialType,
  initialTarget,
  initialSubs,
}: {
  initialType?: string;
  initialTarget?: string;
  initialSubs: Subscription[];
}) {
  const [subs, setSubs] = useState<Subscription[]>(initialSubs);
  const [type, setType] = useState(initialType || 'company');
  const [target, setTarget] = useState(initialTarget || '');
  const [webhookUrl, setWebhookUrl] = useState('');
  const [loading, setLoading] = useState(false);

  const activeCount = useMemo(() => subs.filter((s) => s.is_active).length, [subs]);

  async function createSub() {
    if (!target.trim()) return;
    setLoading(true);
    const res = await fetch(`${API}/subscriptions`, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ subscription_type: type, target_value: target, webhook_url: webhookUrl || null }),
    });
    setLoading(false);
    if (!res.ok) return;
    const created = (await res.json()) as Subscription;
    setSubs([created, ...subs]);
  }

  async function deactivate(id: number) {
    const res = await fetch(`${API}/subscriptions/${id}`, { method: 'DELETE' });
    if (!res.ok) return;
    setSubs(subs.map((s) => (s.id === id ? { ...s, is_active: false } : s)));
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
          <input value={target} onChange={(e) => setTarget(e.target.value)} placeholder="订阅目标" />
          <input value={webhookUrl} onChange={(e) => setWebhookUrl(e.target.value)} placeholder="Webhook URL（可选）" />
          <button onClick={createSub} disabled={loading}>
            {loading ? '提交中...' : '订阅'}
          </button>
        </div>
      </div>

      <div className="card">活跃订阅：{activeCount}</div>

      {subs.map((sub) => (
        <div className="card" key={sub.id}>
          <h3>
            #{sub.id} {sub.subscription_type} / {sub.target_value}
          </h3>
          <p>状态: {sub.is_active ? 'ACTIVE' : 'INACTIVE'}</p>
          <p>最近汇总: {sub.last_digest_date || '-'}</p>
          <p>Webhook: {sub.webhook_url || '-'}</p>
          {sub.is_active && <button onClick={() => deactivate(sub.id)}>停用</button>}
        </div>
      ))}
    </div>
  );
}
