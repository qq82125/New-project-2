'use client';

import { createContext, useContext, useMemo } from 'react';

export type PlanValue = {
  isPro: boolean;
  isAdmin: boolean;
  planStatus: string;
  expiresAt: string | null;
};

const DEFAULT_PLAN: PlanValue = {
  isPro: false,
  isAdmin: false,
  planStatus: 'inactive',
  expiresAt: null,
};

const PlanContext = createContext<PlanValue>(DEFAULT_PLAN);

export function PlanProvider({
  initialPlan,
  children,
}: {
  initialPlan?: Partial<PlanValue> | null;
  children: React.ReactNode;
}) {
  const value = useMemo(() => ({ ...DEFAULT_PLAN, ...(initialPlan || {}) }), [initialPlan]);
  return <PlanContext.Provider value={value}>{children}</PlanContext.Provider>;
}

export function usePlan(): PlanValue {
  return useContext(PlanContext);
}

