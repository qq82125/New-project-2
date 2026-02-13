export type ApiEnvelope<T> = {
  code: number;
  message: string;
  data: T;
};

import 'server-only';
import { headers } from 'next/headers';
import { apiBase } from './api-server';

export async function apiGet<T>(path: string): Promise<{ data: T | null; error: string | null }> {
  try {
    // Forward cookies so API can apply per-user entitlements even for Server Components.
    // Some routes are public, but exporting / pro-only endpoints rely on auth context.
    let cookie = '';
    try {
      cookie = (await headers()).get('cookie') || '';
    } catch {
      cookie = '';
    }

    const res = await fetch(`${apiBase()}${path}`, {
      cache: 'no-store',
      headers: cookie ? { cookie } : undefined,
    });
    if (!res.ok) {
      return { data: null, error: `请求失败 (${res.status})` };
    }
    const body = (await res.json()) as ApiEnvelope<T>;
    if (body.code !== 0) {
      return { data: null, error: body.message || '接口返回异常' };
    }
    return { data: body.data, error: null };
  } catch (err) {
    return { data: null, error: err instanceof Error ? err.message : '网络错误' };
  }
}

export function qs(params: Record<string, string | number | undefined | null>): string {
  const sp = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v === undefined || v === null || v === '') return;
    sp.set(k, String(v));
  });
  const s = sp.toString();
  return s ? `?${s}` : '';
}
