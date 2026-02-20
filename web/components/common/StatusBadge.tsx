import { Badge } from '../ui/badge';
import { STATUS_ZH, labelFrom } from '../../constants/display';

function normalizeStatus(status: string): string {
  return String(status || '').trim().toLowerCase();
}

function statusVariant(status: string): 'success' | 'warning' | 'danger' | 'muted' {
  const value = normalizeStatus(status);
  if (value === 'active' || value === 'valid' || value === 'normal') return 'success';
  if (value === 'expired' || value === 'inactive') return 'warning';
  if (value === 'cancelled' || value === 'revoked' || value === 'invalid') return 'danger';
  return 'muted';
}

export default function StatusBadge({ status }: { status: string | null | undefined }) {
  const raw = String(status || '').trim();
  if (!raw) return <Badge variant="muted">-</Badge>;
  return <Badge variant={statusVariant(raw)}>{labelFrom(STATUS_ZH, raw) || raw}</Badge>;
}
