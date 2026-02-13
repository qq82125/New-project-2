import 'server-only';

import { headers } from 'next/headers';

import { apiBase } from './api-server';

export type MeResponse = {
  user: { id: number; email: string; role: string };
  plan: {
    plan: string;
    plan_status: string;
    plan_expires_at: string | null;
    is_pro: boolean;
    is_admin: boolean;
  };
};

type ApiEnvelope<T> = { code: number; message: string; data: T };

export async function getMe(): Promise<MeResponse | null> {
  const cookie = (await headers()).get('cookie') || '';
  const res = await fetch(`${apiBase()}/api/me`, {
    method: 'GET',
    headers: cookie ? { cookie } : undefined,
    cache: 'no-store',
  });

  if (res.status === 401) return null;
  if (!res.ok) return null;

  try {
    const body = (await res.json()) as ApiEnvelope<MeResponse>;
    if (!body || body.code !== 0) return null;
    return body.data || null;
  } catch {
    return null;
  }
}

