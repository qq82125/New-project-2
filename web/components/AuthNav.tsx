'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Button } from './ui/button';
import { clearAuth, useAuth } from './auth/use-auth';
import { fetchWithProHandling } from '../lib/fetch-client';

export default function AuthNav() {
  const router = useRouter();
  const auth = useAuth();

  const onLogout = async () => {
    await fetchWithProHandling(`/api/auth/logout`, {
      method: 'POST',
      credentials: 'include',
    }).catch(() => null);
    clearAuth();
    router.replace('/login');
    router.refresh();
  };

  if (auth.loading) return null;

  if (!auth.user) {
    return (
      <>
        <Link href="/login" className="app-authlink">
          登录
        </Link>
        <Link href="/register" className="app-authlink">
          注册
        </Link>
      </>
    );
  }

  return (
    <>
      <span className="app-userpill">{auth.user.email}</span>
      <Button variant="ghost" size="sm" type="button" onClick={onLogout}>
        退出
      </Button>
    </>
  );
}
