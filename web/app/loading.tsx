import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Skeleton } from '../components/ui/skeleton';

export default function Loading() {
  return (
    <div className="grid">
      <Card>
        <CardHeader>
          <CardTitle>加载中</CardTitle>
        </CardHeader>
        <CardContent>
          <Skeleton height={14} width={180} />
          <div style={{ height: 10 }} />
          <Skeleton height={12} width={260} />
        </CardContent>
      </Card>

      <div className="columns-2">
        {Array.from({ length: 2 }).map((_, i) => (
          <Card key={i}>
            <CardContent>
              <Skeleton height={12} width={140} />
              <div style={{ height: 10 }} />
              <Skeleton height={24} width={220} />
            </CardContent>
          </Card>
        ))}
      </div>

      <Card>
        <CardContent>
          <Skeleton height={160} />
        </CardContent>
      </Card>
    </div>
  );
}
