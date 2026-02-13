'use client';

import { useMemo, useState } from 'react';

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card';
import { Input } from '../ui/input';
import { Textarea } from '../ui/textarea';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import { toast } from '../ui/use-toast';
import { ErrorState } from '../States';

type AdminConfigItem = {
  config_key: string;
  config_value: any;
  updated_at: string;
};

type ApiResp<T> = { code: number; message: string; data: T };

type ContactInfo = {
  email: string;
  wecom: string;
  form_url: string;
};

function toStr(v: any): string {
  return typeof v === 'string' ? v : '';
}

function sanitizeUrl(v: string): string {
  const s = (v || '').trim();
  if (!s) return '';
  // Keep it simple: allow http(s) only.
  if (s.startsWith('http://') || s.startsWith('https://')) return s;
  return s;
}

export default function ContactInfoManager({ initialConfig }: { initialConfig: AdminConfigItem | null }) {
  const initialValue = useMemo(() => {
    const v = initialConfig?.config_value;
    const obj = v && typeof v === 'object' ? v : {};
    return {
      email: toStr(obj.email).trim(),
      wecom: toStr(obj.wecom).trim(),
      form_url: toStr(obj.form_url).trim(),
    } satisfies ContactInfo;
  }, [initialConfig]);

  const [form, setForm] = useState<ContactInfo>(initialValue);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isValidEmail = useMemo(() => {
    const s = (form.email || '').trim();
    if (!s) return true; // allow empty
    return s.includes('@') && !s.includes(' ');
  }, [form.email]);

  const isValidUrl = useMemo(() => {
    const s = (form.form_url || '').trim();
    if (!s) return true; // allow empty
    try {
      const u = new URL(s);
      return u.protocol === 'http:' || u.protocol === 'https:';
    } catch {
      return false;
    }
  }, [form.form_url]);

  const canSave = isValidEmail && isValidUrl && !saving;

  async function save() {
    if (!canSave) return;
    setSaving(true);
    setError(null);
    try {
      const payload = {
        config_value: {
          email: form.email.trim() || null,
          wecom: form.wecom.trim() || null,
          form_url: sanitizeUrl(form.form_url) || null,
        },
      };

      const res = await fetch('/api/admin/configs/public_contact_info', {
        method: 'PUT',
        credentials: 'include',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify(payload),
      });

      const text = await res.text();
      let parsed: any = null;
      try {
        parsed = JSON.parse(text);
      } catch {
        parsed = null;
      }

      if (!res.ok) {
        const msg = parsed?.detail || parsed?.message || `保存失败 (${res.status})`;
        setError(String(msg));
        toast({ variant: 'destructive', title: '保存失败', description: String(msg) });
        return;
      }

      const body = parsed as ApiResp<AdminConfigItem> | null;
      if (!body || body.code !== 0) {
        const msg = body?.message || '接口返回异常';
        setError(msg);
        toast({ variant: 'destructive', title: '保存失败', description: msg });
        return;
      }

      toast({ title: '已保存', description: '联系方式已更新，/contact 将立即生效（无需重启）。' });
    } catch (e) {
      const msg = e instanceof Error ? e.message : '网络错误';
      setError(msg);
      toast({ variant: 'destructive', title: '网络错误', description: msg });
    } finally {
      setSaving(false);
    }
  }

  function reset() {
    setForm(initialValue);
    toast({ title: '已重置', description: '已恢复为当前数据库里的值（未保存）。' });
  }

  return (
    <div className="grid" style={{ gap: 14 }}>
      <Card>
        <CardHeader>
          <CardTitle>联系信息配置</CardTitle>
          <CardDescription>用于 /contact?intent=pro 与 /contact?intent=trial 页面展示（公开可见）。</CardDescription>
        </CardHeader>
        <CardContent className="grid" style={{ gap: 10 }}>
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
            <Badge variant="muted">config_key: public_contact_info</Badge>
            <Badge variant="muted">留空表示不展示</Badge>
          </div>
          {error ? <ErrorState text={error} /> : null}

          <div className="grid" style={{ gap: 6 }}>
            <div className="muted">邮箱（email）</div>
            <Input
              value={form.email}
              onChange={(e) => setForm((p) => ({ ...p, email: e.target.value }))}
              placeholder="sales@yourcompany.com"
              disabled={saving}
            />
            {!isValidEmail ? <div className="muted" style={{ color: 'var(--danger)' }}>邮箱格式看起来不正确</div> : null}
          </div>

          <div className="grid" style={{ gap: 6 }}>
            <div className="muted">企业微信（wecom，可写 ID / 说明 / 或二维码链接）</div>
            <Textarea
              rows={3}
              value={form.wecom}
              onChange={(e) => setForm((p) => ({ ...p, wecom: e.target.value }))}
              placeholder="例如：扫码添加 / 微信号: xxx / 或 https://..."
              disabled={saving}
            />
          </div>

          <div className="grid" style={{ gap: 6 }}>
            <div className="muted">表单链接（form_url）</div>
            <Input
              value={form.form_url}
              onChange={(e) => setForm((p) => ({ ...p, form_url: e.target.value }))}
              placeholder="https://example.com/form"
              disabled={saving}
            />
            {!isValidUrl ? <div className="muted" style={{ color: 'var(--danger)' }}>链接必须是 http(s) URL</div> : null}
          </div>

          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
            <Button onClick={save} disabled={!canSave}>
              {saving ? '保存中...' : '保存'}
            </Button>
            <Button variant="secondary" onClick={reset} disabled={saving}>
              重置
            </Button>
            <Button
              variant="ghost"
              onClick={() => window.open('/contact?intent=pro', '_blank')}
              disabled={saving}
              title="打开 /contact?intent=pro"
            >
              预览 Pro
            </Button>
            <Button
              variant="ghost"
              onClick={() => window.open('/contact?intent=trial', '_blank')}
              disabled={saving}
              title="打开 /contact?intent=trial"
            >
              预览 Trial
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>当前展示预览</CardTitle>
          <CardDescription>这是 /contact 页会渲染出来的效果（本页预览，不含其它卡片）。</CardDescription>
        </CardHeader>
        <CardContent className="grid" style={{ gap: 8 }}>
          {form.email.trim() ? (
            <div>
              <span className="muted">邮箱：</span>
              <span>{form.email.trim()}</span>
            </div>
          ) : (
            <div className="muted">邮箱：未配置</div>
          )}
          {form.wecom.trim() ? (
            <div>
              <span className="muted">企业微信：</span>
              <span style={{ whiteSpace: 'pre-wrap' }}>{form.wecom.trim()}</span>
            </div>
          ) : (
            <div className="muted">企业微信：未配置</div>
          )}
          {form.form_url.trim() ? (
            <div>
              <span className="muted">表单：</span>
              <a href={form.form_url.trim()} target="_blank" rel="noreferrer" className="muted" style={{ textDecoration: 'underline' }}>
                {form.form_url.trim()}
              </a>
            </div>
          ) : (
            <div className="muted">表单：未配置</div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

