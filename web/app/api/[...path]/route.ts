import { NextRequest } from 'next/server';

import { apiBase } from '../../../lib/api-server';

export const runtime = 'nodejs';
export const dynamic = 'force-dynamic';

const HOP_BY_HOP = new Set([
  'connection',
  'keep-alive',
  'proxy-authenticate',
  'proxy-authorization',
  'te',
  'trailer',
  'transfer-encoding',
  'upgrade',
]);

function copyResponseHeaders(from: Headers): Headers {
  const out = new Headers();
  const anyFrom = from as any;

  // Preserve multiple Set-Cookie headers when available (undici / Next runtime).
  const getSetCookie = anyFrom?.getSetCookie;
  if (typeof getSetCookie === 'function') {
    const cookies: string[] = getSetCookie.call(from) || [];
    for (const c of cookies) out.append('set-cookie', c);
  } else {
    const sc = from.get('set-cookie');
    if (sc) out.set('set-cookie', sc);
  }

  for (const [k, v] of from.entries()) {
    const key = k.toLowerCase();
    if (key === 'set-cookie') continue;
    if (HOP_BY_HOP.has(key)) continue;
    out.set(k, v);
  }

  // Avoid sending invalid transfer metadata when proxying streams.
  out.delete('content-encoding');
  out.delete('content-length');
  return out;
}

async function handler(req: NextRequest, ctx: { params: Promise<{ path: string[] }> }) {
  const { path } = await ctx.params;

  // Same-origin proxy for browser requests; avoids CORS/mixed-content and env base-url issues.
  const upstream = new URL(`${apiBase()}/api/${path.map(encodeURIComponent).join('/')}`);
  upstream.search = req.nextUrl.search;

  if (req.method === 'OPTIONS') {
    return new Response(null, { status: 204 });
  }

  const headers = new Headers();
  const cookie = req.headers.get('cookie');
  if (cookie) headers.set('cookie', cookie);
  const ct = req.headers.get('content-type');
  if (ct) headers.set('content-type', ct);
  const accept = req.headers.get('accept');
  if (accept) headers.set('accept', accept);
  const authorization = req.headers.get('authorization');
  if (authorization) headers.set('authorization', authorization);

  const body = req.method === 'GET' || req.method === 'HEAD' ? undefined : await req.arrayBuffer();
  const res = await fetch(upstream, {
    method: req.method,
    headers,
    body,
    redirect: 'manual',
    cache: 'no-store',
  });

  return new Response(res.body, {
    status: res.status,
    headers: copyResponseHeaders(res.headers),
  });
}

export const GET = handler;
export const POST = handler;
export const PUT = handler;
export const PATCH = handler;
export const DELETE = handler;
