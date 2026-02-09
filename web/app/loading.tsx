import { Card, CardContent, CardHeader, CardTitle } from '../components/ui/card';
import { Skeleton } from '../components/ui/skeleton';

export default function Loading() {
  return (
    <div className="grid">
      <Card>
        <CardHeader>
          <CardTitle>Dashboard</CardTitle>
        </CardHeader>
        <CardContent>
          <Skeleton height={14} width={220} />
          <div style={{ height: 10 }} />
          <Skeleton height={12} width={320} />
        </CardContent>
      </Card>

      <div className="kpis">
        {Array.from({ length: 4 }).map((_, i) => (
          <Card key={i}>
            <CardContent>
              <Skeleton height={12} width={120} />
              <div style={{ height: 10 }} />
              <Skeleton height={30} width={90} />
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="columns-2">
        <Card>
          <CardHeader>
            <CardTitle>趋势</CardTitle>
          </CardHeader>
          <CardContent>
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} style={{ display: 'grid', gridTemplateColumns: '80px 1fr 40px', gap: 10, alignItems: 'center', marginBottom: 10 }}>
                <Skeleton height={10} />
                <Skeleton height={10} />
                <Skeleton height={10} />
              </div>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>榜单</CardTitle>
          </CardHeader>
          <CardContent>
            <Skeleton height={180} />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
