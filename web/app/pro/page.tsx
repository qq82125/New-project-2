import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card';
import UnifiedProGate from '../../components/plan/UnifiedProGate';

export default function ProPage() {
  return (
    <div className="grid">
      <Card>
        <CardHeader>
          <CardTitle>升级方案</CardTitle>
          <CardDescription>Free 与 Pro 权益对比。</CardDescription>
        </CardHeader>
        <CardContent>
          <UnifiedProGate />
        </CardContent>
      </Card>
    </div>
  );
}
