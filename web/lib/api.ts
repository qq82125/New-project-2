export type ApiEnvelope<T> = {
  code: number;
  message: string;
  data: T;
};

// Server components run inside the container, so they must call the API via
// the internal service name (e.g. http://api:8000). Browser calls should use
// NEXT_PUBLIC_API_BASE_URL (e.g. http://localhost:8000).
const API_BASE = process.env.API_BASE_URL || process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

export async function apiGet<T>(path: string): Promise<{ data: T | null; error: string | null }> {
  try {
    // Note: this helper is used in server components too; include cookie when present via next/headers in callers.
    const res = await fetch(`${API_BASE}${path}`, { cache: 'no-store' });
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
