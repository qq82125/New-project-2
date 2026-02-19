import { Card, CardContent, CardHeader } from '../ui/card';
import { Skeleton } from '../ui/skeleton';

export default function DetailPageSkeleton() {
  return (
    <div className="grid">
      <Card>
        <CardHeader>
          <Skeleton width={180} height={20} />
          <Skeleton width={320} height={14} />
        </CardHeader>
        <CardContent className="grid">
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <Skeleton width={90} height={28} />
            <Skeleton width={110} height={28} />
            <Skeleton width={80} height={28} />
          </div>
          <Skeleton height={42} />
          <Skeleton height={42} />
          <Skeleton height={42} />
        </CardContent>
      </Card>
    </div>
  );
}
