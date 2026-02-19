import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card';

export default function SubscriptionsPage() {
  return (
    <div className="grid">
      <Card>
        <CardHeader>
          <CardTitle>订阅与投递</CardTitle>
          <CardDescription>订阅规则、投递通道与历史记录。</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="muted">当前版本为占位页，后续 Phase 将补齐筛选、队列与投递明细。</div>
        </CardContent>
      </Card>
    </div>
  );
}
