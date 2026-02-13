'use client';

import { Badge } from '../ui/badge';
import { usePlan } from './PlanContext';

export default function PlanDebugBadge() {
  const plan = usePlan();
  if (process.env.NODE_ENV === 'production') return null;
  return (
    <Badge variant="muted" title="Dev only">
      DEV plan: {plan.isAdmin ? 'admin' : plan.isPro ? 'pro' : 'free'}
    </Badge>
  );
}

