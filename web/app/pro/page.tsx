import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card';
import UnifiedProGate from '../../components/plan/UnifiedProGate';
import { PRO_SALES_HREF, PRO_TRIAL_HREF } from '../../constants/pro';
import Link from 'next/link';

export default function ProPage() {
  return (
    <div className="grid">
      <Card>
        <CardHeader>
          <h1>升级到 Pro</h1>
          <CardTitle>升级到 Pro</CardTitle>
          <CardDescription>Free vs Pro 权益对比与开通入口。</CardDescription>
        </CardHeader>
        <CardContent className="grid" style={{ gap: 12 }}>
          <UnifiedProGate />
          <div
            className="card"
            style={{
              display: 'flex',
              gap: 10,
              flexWrap: 'wrap',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}
          >
            <div className="muted">企业版支持合同/发票/专属服务。移动端与桌面端均可直接开通。</div>
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
              <Link className="ui-btn ui-btn--secondary ui-btn--sm" href={PRO_SALES_HREF}>
                联系开通
              </Link>
              <Link className="ui-btn ui-btn--default ui-btn--sm" href={PRO_TRIAL_HREF}>
                申请试用
              </Link>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
