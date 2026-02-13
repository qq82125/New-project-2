import { Badge } from '../ui/badge';
import { getMe } from '../../lib/getMe';

export default async function PlanDebugServer() {
  if (process.env.NODE_ENV === 'production') return null;
  const me = await getMe();
  if (!me) return null;
  const isAdmin = Boolean(me.plan?.is_admin);
  const isPro = Boolean(me.plan?.is_pro);
  return (
    <Badge variant="muted" title="Dev only">
      DEV isPro: {isAdmin ? 'admin' : isPro ? 'true' : 'false'}
    </Badge>
  );
}

