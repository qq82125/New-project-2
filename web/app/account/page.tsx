import { headers } from 'next/headers';
import { redirect } from 'next/navigation';

import AccountClient from '../../components/account/AccountClient';

const API_BASE = process.env.API_BASE_URL || process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

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

type MeResp = { code: number; message: string; data: MeData };

export const dynamic = 'force-dynamic';

export default async function AccountPage() {
  const cookie = (await headers()).get('cookie') || '';
  const res = await fetch(`${API_BASE}/api/auth/me`, {
    method: 'GET',
    headers: cookie ? { cookie } : undefined,
    cache: 'no-store',
  });
  if (res.status === 401) redirect('/login');

  let me: MeData | null = null;
  try {
    const body = (await res.json()) as MeResp;
    me = body.data || null;
  } catch {
    me = null;
  }

  return <AccountClient initialMe={me} />;
}
