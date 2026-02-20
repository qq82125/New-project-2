import Link from 'next/link';
import { Card, CardContent } from '../ui/card';

export type KpiCardItem = {
  label: string;
  value: number;
  hint?: string;
  href: string;
};

export default function KpiCard({ label, value, hint, href }: KpiCardItem) {
  return (
    <Link href={href} style={{ color: 'inherit' }}>
      <Card>
        <CardContent>
          <div className="muted" style={{ fontSize: 12 }}>{label}</div>
          <div style={{ fontSize: 30, fontWeight: 800, lineHeight: 1.1, marginTop: 4 }}>{value}</div>
          {hint ? <div className="muted" style={{ fontSize: 12, marginTop: 8 }}>{hint}</div> : null}
        </CardContent>
      </Card>
    </Link>
  );
}

