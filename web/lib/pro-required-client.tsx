'use client';

import { toast } from '../components/ui/use-toast';
import { PRO_COPY, PRO_TRIAL_HREF } from '../constants/pro';

function isProRequiredPayload(body: any): boolean {
  const code = body?.detail?.code || body?.code || body?.error;
  return String(code || '').toUpperCase() === 'PRO_REQUIRED';
}

export async function handleProRequiredResponse(res: Response): Promise<boolean> {
  if (!(res.status === 402 || res.status === 403)) return false;

  let body: any = null;
  try {
    body = await res.clone().json();
  } catch {
    body = null;
  }

  if (!isProRequiredPayload(body)) return false;

  toastProRequiredAndRedirect();
  return true;
}

export function toastProRequired(): void {
  toast({ title: PRO_COPY.toast.pro_required_title, description: PRO_COPY.toast.pro_required_desc });
}

export function toastProRequiredAndRedirect(): void {
  toastProRequired();
  setTimeout(() => {
    window.location.href = PRO_TRIAL_HREF;
  }, 350);
}

export function toastComingSoon(): void {
  toast({ title: PRO_COPY.toast.coming_soon_title, description: PRO_COPY.toast.coming_soon_desc });
}
