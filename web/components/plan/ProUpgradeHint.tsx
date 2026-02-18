import Link from 'next/link';
import { Card, CardContent } from '../ui/card';
import { Badge } from '../ui/badge';
import { PRO_COPY, PRO_TRIAL_HREF } from '../../constants/pro';

export default function ProUpgradeHint({
  text,
  highlights,
  ctaHref = PRO_TRIAL_HREF,
  ctaLabel = PRO_COPY.banner.free_cta,
}: {
  text: string;
  highlights?: string[];
  ctaHref?: string;
  ctaLabel?: string;
}) {
  const chips = (highlights || []).map((x) => String(x || '').trim()).filter(Boolean).slice(0, 6);
  return (
    <Card>
      <CardContent className="grid" style={{ gap: 10 }}>
        <div className="muted">{text}</div>
        {chips.length ? (
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
            {chips.map((t) => (
              <Badge key={t} variant="muted">
                {t}
              </Badge>
            ))}
          </div>
        ) : null}
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
          <Badge variant="muted">专业版</Badge>
          <Link className="ui-btn ui-btn--default ui-btn--sm" href={ctaHref}>
            {ctaLabel}
          </Link>
        </div>
      </CardContent>
    </Card>
  );
}
