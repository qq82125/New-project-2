import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Skeleton } from '../../components/ui/skeleton';

export default function Loading() {
  return (
    <div className="grid">
      <Card>
        <CardHeader>
          <CardTitle>管理后台</CardTitle>
        </CardHeader>
        <CardContent>
          <Skeleton height={12} width={260} />
          <div style={{ height: 10 }} />
          <Skeleton height={12} width={340} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>当前登录用户</CardTitle>
        </CardHeader>
        <CardContent style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
          <Skeleton height={26} width={60} />
          <Skeleton height={26} width={180} />
          <Skeleton height={26} width={70} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>最近一次同步</CardTitle>
        </CardHeader>
        <CardContent>
          <Skeleton height={26} width={320} />
          <div style={{ height: 10 }} />
          <Skeleton height={12} width={220} />
        </CardContent>
      </Card>
    </div>
  );
}

