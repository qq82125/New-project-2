'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';

type MeData = {
  id: number;
  email: string;
  role: string;
};

type AuthState =
  | { loading: true; user: null }
  | { loading: false; user: MeData | null };

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

export default function AuthNav() {
  const router = useRouter();
  const [auth, setAuth] = useState<AuthState>({ loading: true, user: null });

  useEffect(() => {
    let mounted = true;
    const fetchMe = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/auth/me`, {
          method: 'GET',
          credentials: 'include',
        });
        if (!mounted) return;
        if (!res.ok) {
          setAuth({ loading: false, user: null });
          return;
        }
        const body = await res.json();
        setAuth({ loading: false, user: body?.data || null });
      } catch {
        if (mounted) setAuth({ loading: false, user: null });
      }
    };

    fetchMe();
    return () => {
      mounted = false;
    };
  }, []);

  const onLogout = async () => {
    await fetch(`${API_BASE}/api/auth/logout`, {
      method: 'POST',
      credentials: 'include',
    });
    setAuth({ loading: false, user: null });
    router.refresh();
  };

  if (auth.loading) return null;

  if (!auth.user) {
    return (
      <>
        <Link href="/login">登录</Link>
        <Link href="/register">注册</Link>
      </>
    );
  }

  return (
    <>
      <span>{auth.user.email}</span>
      <button type="button" onClick={onLogout}>
        退出
      </button>
    </>
  );
}
