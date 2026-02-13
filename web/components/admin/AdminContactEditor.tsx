'use client';

import { useMemo, useState } from 'react';

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card';
import { Input } from '../ui/input';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import { toast } from '../ui/use-toast';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

type ContactInfo = {
  email?: string;
  wecom?: string;
  form_url?: string;
  note?: string;
};

type ApiResp<T> = { code: number; message: string; data: T };

export default function AdminContactEditor({ initialValue }: { initialValue: Record<string, any> }) {
  const initial = useMemo((): ContactInfo => {
    const v = (initialValue || {}) as ContactInfo;
    return {
      email: v.email || '',
      wecom: v.wecom || '',
      form_url: v.form_url || '',
      note: v.note || '',
    };
  }, [initialValue]);

  const [loading, setLoading] = useState(false);
  const [form, setForm] = useState<ContactInfo>(initial);

  async function save() {
    setLoading(true);
    try {
      const payload = { config_value: { ...form } };
      const res = await fetch(`${API_BASE}/api/admin/configs/contact_info`, {
        method: 'PUT',
        headers: { 'content-type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        toast({ variant: 'destructive', title: '保存失败', description: `HTTP ${res.status}` });
        return;
      }
      const body = (await res.json()) as ApiResp<{ config_key: string }>;
      if (body.code !== 0) {
        toast({ variant: 'destructive', title: '保存失败', description: body.message || '接口返回异常' });
        return;
      }
      toast({ title: '已保存', description: 'contact_info 已更新' });
    } catch (e) {
      toast({ variant: 'destructive', title: '网络错误', description: e instanceof Error ? e.message : '网络错误' });
    } finally {
      setLoading(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>联系信息</CardTitle>
        <CardDescription>写入 admin_configs.contact_info（JSON）。</CardDescription>
      </CardHeader>
      <CardContent className="grid">
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
          <Badge variant="muted">config_key: contact_info</Badge>
          <Button onClick={save} disabled={loading}>
            保存
          </Button>
        </div>

        <div className="grid" style={{ gap: 10 }}>
          <div>
            <div className="muted">邮箱</div>
            <Input value={form.email || ''} onChange={(e) => setForm((p) => ({ ...p, email: e.target.value }))} />
          </div>
          <div>
            <div className="muted">企业微信</div>
            <Input value={form.wecom || ''} onChange={(e) => setForm((p) => ({ ...p, wecom: e.target.value }))} />
          </div>
          <div>
            <div className="muted">表单链接</div>
            <Input
              value={form.form_url || ''}
              onChange={(e) => setForm((p) => ({ ...p, form_url: e.target.value }))}
              placeholder="https://..."
            />
          </div>
          <div>
            <div className="muted">备注</div>
            <Input value={form.note || ''} onChange={(e) => setForm((p) => ({ ...p, note: e.target.value }))} />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

