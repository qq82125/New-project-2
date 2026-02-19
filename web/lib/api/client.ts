export class ApiHttpError extends Error {
  status: number;
  responseText: string;

  constructor(status: number, responseText: string) {
    super(`apiGet failed: ${status} ${responseText}`);
    this.name = 'ApiHttpError';
    this.status = status;
    this.responseText = responseText;
  }
}

function getApiBase(): string {
  const base =
    (typeof window === 'undefined' ? process.env.API_BASE_URL : undefined) ||
    process.env.NEXT_PUBLIC_API_BASE_URL ||
    '';
  return base.replace(/\/+$/, '');
}

function buildUrl(path: string, params?: Record<string, string>): string {
  const base = getApiBase();
  const fullPath = path.startsWith('http://') || path.startsWith('https://') ? path : `${base}${path}`;
  if (!params || Object.keys(params).length === 0) return fullPath;

  const url = new URL(fullPath, typeof window === 'undefined' ? 'http://localhost' : window.location.origin);
  Object.entries(params).forEach(([key, value]) => {
    if (value !== '') url.searchParams.set(key, value);
  });

  if (path.startsWith('http://') || path.startsWith('https://') || base) return url.toString();
  return `${path}${url.search}`;
}

export async function apiGet<T>(path: string, params?: Record<string, string>): Promise<T> {
  const url = buildUrl(path, params);
  const res = await fetch(url, { method: 'GET', cache: 'no-store' });
  if (!res.ok) {
    const text = await res.text();
    throw new ApiHttpError(res.status, text);
  }
  return (await res.json()) as T;
}
