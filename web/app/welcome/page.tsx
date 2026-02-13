import { headers } from 'next/headers';
import { redirect } from 'next/navigation';

import WelcomeClient from '../../components/welcome/WelcomeClient';

import { apiBase } from '../../lib/api-server';

export const dynamic = 'force-dynamic';

export default async function WelcomePage() {
  const API_BASE = apiBase();
  const cookie = (await headers()).get('cookie') || '';
  const res = await fetch(`${API_BASE}/api/auth/me`, {
    method: 'GET',
    headers: cookie ? { cookie } : undefined,
    cache: 'no-store',
  });
  if (res.status === 401) redirect('/login');
  // If backend returns other errors, just show client page (it will still render the comparison).

  return <WelcomeClient />;
}
