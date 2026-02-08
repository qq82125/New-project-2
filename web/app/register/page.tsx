'use client';

import { FormEvent, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Input } from '../../components/ui/input';
import { Button } from '../../components/ui/button';
import { toast } from '../../components/ui/use-toast';
import { refreshAuth } from '../../components/auth/use-auth';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

export default function RegisterPage() {
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const onSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      const res = await fetch(`${API_BASE}/api/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ email, password }),
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        const msg = body?.detail || `注册失败 (${res.status})`;
        setError(msg);
        toast({ variant: 'destructive', title: '注册失败', description: msg });
        return;
      }
      // Refresh client-side auth state so header/side-nav immediately reflect login.
      await refreshAuth();
      router.push('/welcome');
      router.refresh();
    } catch (err) {
      const msg = err instanceof Error ? err.message : '网络错误';
      setError(msg);
      toast({ variant: 'destructive', title: '网络错误', description: msg });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>注册</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={onSubmit} className="grid">
          <Input
          type="email"
          placeholder="邮箱"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          />
          <Input
          type="password"
          placeholder="密码（至少8位）"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          minLength={8}
          required
          />
          <Button type="submit" disabled={submitting}>
            {submitting ? '注册中...' : '注册'}
          </Button>
        </form>
        {error ? <p className="muted" style={{ marginTop: 10 }}>{error}</p> : null}
        <p className="muted" style={{ marginTop: 10 }}>
          已有账号？<Link href="/login">去登录</Link>
        </p>
      </CardContent>
    </Card>
  );
}
