import { headers } from 'next/headers';
import { redirect } from 'next/navigation';

import WelcomeClient from '../../components/welcome/WelcomeClient';

const API_BASE = process.env.API_BASE_URL || process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

export const dynamic = 'force-dynamic';

export default async function WelcomePage() {
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

