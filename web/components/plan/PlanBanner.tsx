import Link from 'next/link';
import { Badge } from '../ui/badge';
import { PRO_COPY, PRO_TRIAL_HREF } from '../../constants/pro';

export default function PlanBanner({ isPro }: { isPro: boolean }) {
  const title = isPro ? PRO_COPY.banner.pro_title : PRO_COPY.banner.free_title;
  const subtitle = isPro ? PRO_COPY.banner.pro_subtitle : PRO_COPY.banner.free_subtitle;

  return (
    <div
      style={{
        border: '1px solid rgba(207, 224, 213, 0.9)',
        borderRadius: 14,
        padding: 14,
        background:
          'radial-gradient(circle at 0% 0%, rgba(23, 107, 82, 0.12) 0%, transparent 60%), rgba(255, 255, 255, 0.86)',
        boxShadow: 'var(--shadow-sm)',
        display: 'flex',
        gap: 12,
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
      }}
    >
      <div style={{ minWidth: 240 }}>
        <div style={{ fontWeight: 800, letterSpacing: 0.1 }}>{title}</div>
        <div className="muted" style={{ marginTop: 6 }}>
          {subtitle}
        </div>
      </div>

      <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
        {isPro ? (
          <Badge variant="success">Pro</Badge>
        ) : (
          <>
            <Badge variant="muted">Free</Badge>
            <Link className="ui-btn ui-btn--default ui-btn--sm" href={PRO_TRIAL_HREF}>
              {PRO_COPY.banner.free_cta}
            </Link>
          </>
        )}
      </div>
    </div>
  );
}
