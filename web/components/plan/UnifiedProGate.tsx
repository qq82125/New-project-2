import Link from 'next/link';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Badge } from '../ui/badge';
import { PRO_SALES_HREF, PRO_TRIAL_HREF } from '../../constants/pro';

const BENEFITS = [
  { key: '导出 CSV', free: '不可用', pro: '可用' },
  { key: '订阅投递', free: '基础', pro: '高级策略' },
  { key: '高级筛选', free: '基础筛选', pro: '全量条件' },
  { key: '风险信号', free: '摘要', pro: '完整证据链' },
];

export default function UnifiedProGate() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>升级到 Pro</CardTitle>
      </CardHeader>
      <CardContent className="grid" style={{ gap: 10 }}>
        <div className="muted">解锁导出与高级分析能力</div>
        <div className="grid" style={{ gap: 8 }}>
          {BENEFITS.map((item) => (
            <div
              key={item.key}
              style={{
                display: 'grid',
                gap: 8,
                gridTemplateColumns: 'minmax(120px, 1fr) minmax(80px, auto) minmax(80px, auto)',
                alignItems: 'center',
              }}
            >
              <span>{item.key}</span>
              <Badge variant="muted">Free: {item.free}</Badge>
              <Badge variant="success">Pro: {item.pro}</Badge>
            </div>
          ))}
        </div>
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
          <Link className="ui-btn ui-btn--secondary ui-btn--sm" href={PRO_SALES_HREF}>
            联系开通
          </Link>
          <Link className="ui-btn ui-btn--default ui-btn--sm" href={PRO_TRIAL_HREF}>
            申请试用
          </Link>
        </div>
      </CardContent>
    </Card>
  );
}
