import 'server-only';

import { headers } from 'next/headers';
import { notFound, redirect } from 'next/navigation';

import { apiBase } from './api-server';

export type AdminMe = { id: number; email: string; role: string };
type ApiEnvelope<T> = { code: number; message: string; data: T };

type AdminFetchInit = RequestInit & { allowNotOk?: boolean };

export async function adminFetch(path: string, init?: AdminFetchInit): Promise<Response> {
  const cookie = (await headers()).get('cookie') || '';
  const { allowNotOk, ...fetchInit } = init || {};

  const h = new Headers(fetchInit.headers || undefined);
  if (cookie && !h.has('cookie')) {
    h.set('cookie', cookie);
  }

  const res = await fetch(`${apiBase()}${path}`, {
    method: fetchInit.method || 'GET',
    cache: 'no-store',
    ...fetchInit,
    headers: h,
  });

  if (res.status === 401) redirect('/login');
  if (res.status === 403) notFound();
  if (!allowNotOk && !res.ok) throw new Error(`admin api failed: ${path} (${res.status})`);
  return res;
}

export async function adminFetchJson<T>(path: string, init?: AdminFetchInit): Promise<T> {
  const res = await adminFetch(path, init);
  const body = (await res.json()) as ApiEnvelope<T>;
  if (body.code !== 0) {
    throw new Error(body.message || `admin api returned error: ${path}`);
  }
  return body.data;
}

export async function getAdminMe(): Promise<AdminMe> {
  return adminFetchJson<AdminMe>('/api/admin/me');
}

