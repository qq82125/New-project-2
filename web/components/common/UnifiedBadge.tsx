import { Badge } from '../ui/badge';

export type UnifiedBadgeToken = {
  kind: 'risk' | 'change' | 'track' | 'custom';
  value: string;
};

function normalize(v: string): string {
  return String(v || '').trim();
}

function riskVariant(v: string): 'danger' | 'warning' | 'success' | 'muted' {
  const x = normalize(v).toLowerCase();
  if (x.includes('high') || x.includes('critical')) return 'danger';
  if (x.includes('mid') || x.includes('medium')) return 'warning';
  if (x.includes('low')) return 'success';
  return 'muted';
}

function changeVariant(v: string): 'danger' | 'warning' | 'success' | 'muted' {
  const x = normalize(v).toLowerCase();
  if (x === 'new') return 'success';
  if (x === 'update') return 'warning';
  if (x === 'cancel') return 'danger';
  return 'muted';
}

export default function UnifiedBadge({ token }: { token: UnifiedBadgeToken }) {
  if (!token.value) return null;
  if (token.kind === 'risk') return <Badge variant={riskVariant(token.value)}>{token.value}</Badge>;
  if (token.kind === 'change') return <Badge variant={changeVariant(token.value)}>{token.value}</Badge>;
  if (token.kind === 'track') return <Badge variant="muted">{token.value}</Badge>;
  return <Badge variant="muted">{token.value}</Badge>;
}

