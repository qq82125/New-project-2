import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card';
import UnifiedProGate from '../../components/plan/UnifiedProGate';

export default function ProPage() {
  return (
    <div className="grid">
      <Card>
        <CardHeader>
          <CardTitle data-testid="pro__header__title">升级到 Pro</CardTitle>
          <CardDescription>Free 与 Pro 权益对比。</CardDescription>
        </CardHeader>
        <CardContent>
          <UnifiedProGate />
        </CardContent>
      </Card>
    </div>
  );
}
