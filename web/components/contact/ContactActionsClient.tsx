'use client';

import { useMemo } from 'react';

import { Button } from '../ui/button';
import { toast } from '../ui/use-toast';
import { useAuth } from '../auth/use-auth';

type ContactInfo = {
  email?: string | null;
  wecom?: string | null;
  form_url?: string | null;
};

function safeTrim(s?: string | null): string {
  return (s || '').trim();
}

async function copyToClipboard(text: string) {
  const t = (text || '').trim();
  if (!t) return false;
  try {
    await navigator.clipboard.writeText(t);
    return true;
  } catch {
    return false;
  }
}

export default function ContactActionsClient({
  intent,
  info,
}: {
  intent: 'trial' | 'pro' | 'other';
  info: ContactInfo;
}) {
  const auth = useAuth();
  const isAdmin = !auth.loading && auth.user?.role === 'admin';

  const email = safeTrim(info.email);
  const wecom = safeTrim(info.wecom);
  const formUrl = safeTrim(info.form_url);

  const primaryLabel = useMemo(() => {
    if (intent === 'trial') return '提交试用申请';
    if (intent === 'pro') return '申请开通 Pro';
    return '提交申请';
  }, [intent]);

  const mailSubject = useMemo(() => {
    if (intent === 'trial') return '试用申请';
    if (intent === 'pro') return '开通 Pro';
    return '联系';
  }, [intent]);

  const mailBody = useMemo(() => {
    if (intent === 'trial') return '请简单描述：公司/团队、试用周期、订阅规模、核心需求。';
    if (intent === 'pro') return '请简单描述：公司/团队、开通周期、订阅规模、是否需要周报/导出。';
    return '请简单描述需求。';
  }, [intent]);

  const canPrimary = Boolean(formUrl || email);

  return (
    <div className="grid" style={{ gap: 10 }}>
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
        <Button
          disabled={!canPrimary}
          onClick={() => {
            if (formUrl) {
              window.open(formUrl, '_blank', 'noreferrer');
              return;
            }
            if (email) {
              const href = `mailto:${encodeURIComponent(email)}?subject=${encodeURIComponent(mailSubject)}&body=${encodeURIComponent(mailBody)}`;
              window.location.href = href;
            }
          }}
          title={formUrl ? '打开表单链接' : email ? '使用邮件联系' : '未配置联系方式'}
        >
          {primaryLabel}
        </Button>

        <Button
          variant="secondary"
          disabled={!email}
          onClick={() => {
            if (!email) return;
            const href = `mailto:${encodeURIComponent(email)}?subject=${encodeURIComponent(mailSubject)}&body=${encodeURIComponent(mailBody)}`;
            window.location.href = href;
          }}
          title={email ? '用默认邮件客户端发送' : '未配置邮箱'}
        >
          邮件联系
        </Button>

        <Button
          variant="ghost"
          disabled={!email}
          onClick={async () => {
            if (!email) return;
            const ok = await copyToClipboard(email);
            if (ok) toast({ title: '已复制邮箱', description: email });
            else toast({ variant: 'destructive', title: '复制失败', description: '浏览器不支持或权限受限' });
          }}
          title={email ? '复制邮箱' : '未配置邮箱'}
        >
          复制邮箱
        </Button>

        <Button
          variant="ghost"
          disabled={!wecom}
          onClick={async () => {
            if (!wecom) return;
            const ok = await copyToClipboard(wecom);
            if (ok) toast({ title: '已复制企业微信', description: '可直接粘贴到聊天中' });
            else toast({ variant: 'destructive', title: '复制失败', description: '浏览器不支持或权限受限' });
          }}
          title={wecom ? '复制企业微信内容' : '未配置企业微信'}
        >
          复制企业微信
        </Button>
      </div>

      {isAdmin ? (
        <div className="muted" style={{ fontSize: 13 }}>
          管理员入口：
          <a href="/admin/contact" className="muted" style={{ textDecoration: 'underline', marginLeft: 6 }}>
            编辑联系方式
          </a>
        </div>
      ) : null}
    </div>
  );
}
