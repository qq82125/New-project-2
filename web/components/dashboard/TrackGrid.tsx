import Link from 'next/link';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card';

export type TrackGridItem = {
  id: string;
  name: string;
  description?: string;
  href: string;
};

export default function TrackGrid({ tracks }: { tracks: TrackGridItem[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Track Entry</CardTitle>
        <CardDescription>赛道入口卡片，点击后按 track 进入 Search。</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="columns-3">
          {tracks.map((track) => (
            <Link key={track.id} href={track.href} style={{ color: 'inherit' }}>
              <div className="card" style={{ minHeight: 88 }}>
                <div style={{ fontWeight: 700 }}>{track.name}</div>
                {track.description ? <div className="muted" style={{ marginTop: 6 }}>{track.description}</div> : null}
              </div>
            </Link>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

