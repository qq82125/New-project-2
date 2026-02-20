import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Skeleton } from '../../components/ui/skeleton';

export default function Loading() {
  return (
    <div className="grid">
      <Card>
        <CardHeader>
          <CardTitle>搜索</CardTitle>
        </CardHeader>
        <CardContent className="grid">
          <Skeleton height={38} />
          <Skeleton height={42} />
        </CardContent>
      </Card>

      <Card>
        <CardContent style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
          <Skeleton width={120} height={22} />
          <Skeleton width={180} height={22} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>结果列表</CardTitle>
        </CardHeader>
        <CardContent className="grid">
          {Array.from({ length: 8 }).map((_, i) => (
            <Skeleton key={i} height={34} />
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
