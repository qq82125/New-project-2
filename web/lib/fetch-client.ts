'use client';

import { handleProRequiredResponse } from './pro-required-client';

export async function fetchWithProHandling(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  const res = await fetch(input, init);
  await handleProRequiredResponse(res);
  return res;
}

