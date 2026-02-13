import Link from 'next/link';

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';

import { apiBase } from '../../lib/api-server';
import ContactActionsClient from '../../components/contact/ContactActionsClient';

type ContactInfo = { email?: string | null; wecom?: string | null; form_url?: string | null };
type ContactInfoResp = { code: number; message: string; data: ContactInfo };

export const dynamic = 'force-dynamic';

export default async function ContactPage({ searchParams }: { searchParams: Promise<{ intent?: string }> }) {
  const { intent } = await searchParams;
  const tag = intent === 'trial' ? '试用申请' : intent === 'pro' ? '开通 Pro' : '联系';
  const intentKey = intent === 'trial' ? 'trial' : intent === 'pro' ? 'pro' : 'other';

  // Public endpoint: admins can edit via /admin/contact.
  let info: ContactInfo | null = null;
  try {
    const res = await fetch(`${apiBase()}/api/public/contact-info`, { cache: 'no-store' });
    if (res.ok) {
      const body = (await res.json()) as ContactInfoResp;
      if (body && body.code === 0) info = body.data || null;
    }
  } catch {
    info = null;
  }

  const hasAny = Boolean(info?.email || info?.wecom || info?.form_url);
  const email = hasAny ? (info?.email || null) : 'sales@example.com';
  const wecom = hasAny ? (info?.wecom || null) : '（占位）扫码/ID';
  const formUrl = hasAny ? (info?.form_url || null) : 'https://example.com/form';

  return (
    <div className="grid">
      <Card>
        <CardHeader>
          <CardTitle>联系与申请</CardTitle>
          <CardDescription>
            {intentKey === 'trial'
              ? '试用申请入口。建议优先走表单，信息更完整。'
              : intentKey === 'pro'
                ? '开通 Pro 入口。建议留下公司与需求，便于快速对接。'
                : '联系入口。'}
          </CardDescription>
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
          <CardTitle>快速入口</CardTitle>
          <CardDescription>一键打开表单、发送邮件或复制信息。</CardDescription>
        </CardHeader>
        <CardContent className="grid" style={{ gap: 10 }}>
          <ContactActionsClient intent={intentKey} info={{ email: email || null, wecom: wecom || null, form_url: formUrl || null }} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>联系方式</CardTitle>
          <CardDescription>建议优先邮件，便于留档。</CardDescription>
        </CardHeader>
        <CardContent className="grid">
          {email ? (
            <div>
              <span className="muted">邮箱：</span>
              <span>{email}</span>
            </div>
          ) : null}
          {wecom ? (
            <div>
              <span className="muted">企业微信：</span>
              <span style={{ whiteSpace: 'pre-wrap' }}>{wecom}</span>
            </div>
          ) : null}
          {formUrl ? (
            <div>
              <span className="muted">表单：</span>
              <a href={formUrl} target="_blank" rel="noreferrer" className="muted" style={{ textDecoration: 'underline' }}>
                {formUrl}
              </a>
            </div>
          ) : null}
          {!email && !wecom && !formUrl ? <div className="muted">暂无联系信息</div> : null}
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
