import { headers } from 'next/headers';
import { redirect } from 'next/navigation';

import AccountClient from '../../components/account/AccountClient';

import { apiBase } from '../../lib/api-server';
import { getMe } from '../../lib/getMe';

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

type MeResp = { code: number; message: string; data: MeData };

export const dynamic = 'force-dynamic';

export default async function AccountPage() {
  const API_BASE = apiBase();
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

  const me2 = await getMe();
  if (me2?.plan) {
    me = {
      ...(me || {}),
      plan: me2.plan.plan,
      plan_status: me2.plan.plan_status,
      plan_expires_at: me2.plan.plan_expires_at,
      is_pro: me2.plan.is_pro,
      is_admin: me2.plan.is_admin,
    };
  }

  return <AccountClient initialMe={me} />;
}
