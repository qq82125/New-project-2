import Link from 'next/link';

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';

export const dynamic = 'force-dynamic';

export default async function ContactPage({ searchParams }: { searchParams: Promise<{ intent?: string }> }) {
  const { intent } = await searchParams;
  const tag = intent === 'trial' ? '试用申请' : intent === 'pro' ? '开通 Pro' : '联系';

  return (
    <div className="grid">
      <Card>
        <CardHeader>
          <CardTitle>联系与申请</CardTitle>
          <CardDescription>ToB 开通与试用申请（占位信息，可按实际渠道替换）。</CardDescription>
        </CardHeader>
        <CardContent style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
          <Badge variant="muted">{tag}</Badge>
          <Badge variant="muted">
            <Link href="/welcome">返回引导页</Link>
          </Badge>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>联系方式</CardTitle>
          <CardDescription>建议优先邮件，便于留档。</CardDescription>
        </CardHeader>
        <CardContent className="grid">
          <div>
            <span className="muted">邮箱：</span>sales@example.com
          </div>
          <div>
            <span className="muted">企业微信：</span>（占位）扫码/ID
          </div>
          <div>
            <span className="muted">表单：</span>（占位）https://example.com/form
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>你可以提供的信息</CardTitle>
          <CardDescription>帮助我们更快评估试用或开通。</CardDescription>
        </CardHeader>
        <CardContent className="grid">
          <div className="muted">1) 公司/团队名称</div>
          <div className="muted">2) 订阅规模（企业/关键词数量）</div>
          <div className="muted">3) 是否需要行业周报、导出、到期风险提醒</div>
          <div className="muted">4) 期望开通周期（年度/试用）</div>
        </CardContent>
      </Card>
    </div>
  );
}

