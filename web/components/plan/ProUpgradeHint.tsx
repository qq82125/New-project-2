import Link from 'next/link';
import { Card, CardContent } from '../ui/card';
import { Badge } from '../ui/badge';
import { PRO_COPY, PRO_TRIAL_HREF } from '../../constants/pro';

export default function ProUpgradeHint({
  text,
  ctaHref = PRO_TRIAL_HREF,
  ctaLabel = PRO_COPY.banner.free_cta,
}: {
  text: string;
  ctaHref?: string;
  ctaLabel?: string;
}) {
  return (
    <Card>
      <CardContent className="grid" style={{ gap: 10 }}>
        <div className="muted">{text}</div>
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
          <Badge variant="muted">Pro</Badge>
          <Link className="ui-btn ui-btn--default ui-btn--sm" href={ctaHref}>
            {ctaLabel}
          </Link>
        </div>
      </CardContent>
    </Card>
  );
}
