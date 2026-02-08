'use client';

import { useEffect, useState } from 'react';

export type MeData = {
  id: number;
  email: string;
  role: string;
  plan?: string;
  plan_status?: string;
  plan_expires_at?: string | null;
  entitlements?: {
    can_export: boolean;
    max_subscriptions: number;
    trend_range_days: number;
  } | null;
  onboarded?: boolean;
};

type AuthState =
  | { loading: true; user: null }
  | { loading: false; user: MeData | null };

type Listener = (state: AuthState) => void;

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

let memoryState: AuthState = { loading: true, user: null };
const listeners = new Set<Listener>();

function emit() {
  listeners.forEach((l) => l(memoryState));
}

function setState(next: AuthState) {
  memoryState = next;
  emit();
}

export async function refreshAuth() {
  try {
    const res = await fetch(`${API_BASE}/api/auth/me`, {
      method: 'GET',
      credentials: 'include',
      cache: 'no-store',
    });
    if (!res.ok) {
      setState({ loading: false, user: null });
      return;
    }
    const body = await res.json();
    setState({ loading: false, user: body?.data || null });
  } catch {
    setState({ loading: false, user: null });
  }
}

export function clearAuth() {
  setState({ loading: false, user: null });
}

export function useAuth() {
  const [state, setLocal] = useState<AuthState>(memoryState);

  useEffect(() => {
    listeners.add(setLocal);
    // Best-effort refresh on first subscription.
    if (memoryState.loading) void refreshAuth();
    return () => {
      listeners.delete(setLocal);
    };
  }, []);

  return state;
}
