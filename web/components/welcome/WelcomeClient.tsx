'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';

import { Badge } from '../ui/badge';
import { Button } from '../ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card';
import { Table, TableWrap } from '../ui/table';
import { toast } from '../ui/use-toast';
import { useAuth, refreshAuth } from '../auth/use-auth';
import { fetchWithProHandling } from '../../lib/fetch-client';
import { PLAN_STATUS_ZH, PLAN_ZH, labelFrom } from '../../constants/display';

async function markOnboardedBestEffort() {
  try {
    await fetchWithProHandling(`/api/users/onboarded`, { method: 'POST', credentials: 'include' });
    await refreshAuth();
  } catch {
    // ignore
  }
}

export default function WelcomeClient() {
  const router = useRouter();
  const auth = useAuth();
  const [marking, setMarking] = useState(false);

  useEffect(() => {
    if (!auth.loading && !auth.user) router.replace('/login');
  }, [auth.loading, auth.user, router]);

  const go = async (path: string) => {
    setMarking(true);
    await markOnboardedBestEffort();
    setMarking(false);
    router.push(path);
    router.refresh();
  };

  const onContact = async () => {
    toast({ title: '联系开通', description: '即将跳转到联系方式页（ToB 开通）。' });
    await go('/contact?intent=pro');
  };

  const onTrial = async () => {
    toast({ title: '申请试用', description: '即将跳转到试用申请页（表单占位）。' });
    await go('/contact?intent=trial');
  };

  const onLater = async () => {
    await go('/');
  };

  return (
    <div className="grid">
      <Card>
        <CardHeader>
          <CardTitle>欢迎使用 DeepIVD</CardTitle>
          <CardDescription>您当前为免费版用户，以下是您可用的功能与升级选项</CardDescription>
        </CardHeader>
        <CardContent style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
          {auth.user ? (
            <>
              <Badge variant="muted">{auth.user.email}</Badge>
              <Badge variant="muted">
                当前计划：{labelFrom(PLAN_ZH, auth.user.plan || 'free')} / {labelFrom(PLAN_STATUS_ZH, auth.user.plan_status || 'inactive')}
              </Badge>
            </>
          ) : (
            <Badge variant="muted">未登录</Badge>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>权益对比</CardTitle>
          <CardDescription>免费版与专业版（年度）的能力差异（后端强校验）。</CardDescription>
        </CardHeader>
        <CardContent>
          <TableWrap>
            <Table>
              <thead>
                <tr>
                  <th>功能</th>
                  <th style={{ width: 160 }}>免费版</th>
                  <th style={{ width: 200 }}>专业版（年度）</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>仪表盘行业概览</td>
                  <td>✅</td>
                  <td>✅</td>
                </tr>
                <tr>
                  <td>行业周报（自动推送）</td>
                  <td>❌</td>
                  <td>✅</td>
                </tr>
                <tr>
                  <td>订阅企业/关键词</td>
                  <td>3 个</td>
                  <td>50 个</td>
                </tr>
                <tr>
                  <td>趋势分析周期</td>
                  <td>30 天</td>
                  <td>365 天</td>
                </tr>
                <tr>
                  <td>数据导出</td>
                  <td>❌</td>
                  <td>✅</td>
                </tr>
                <tr>
                  <td>到期风险提醒</td>
                  <td>❌</td>
                  <td>✅</td>
                </tr>
              </tbody>
            </Table>
          </TableWrap>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>升级方式（ToB）</CardTitle>
          <CardDescription>不接支付。请通过联系/试用申请开通。</CardDescription>
        </CardHeader>
        <CardContent className="grid" style={{ gap: 10 }}>
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
            <Button type="button" onClick={onContact} disabled={marking || auth.loading || !auth.user}>
              联系开通专业版（年度）
            </Button>
            <Button type="button" variant="secondary" onClick={onTrial} disabled={marking || auth.loading || !auth.user}>
              申请试用
            </Button>
            <Badge variant="muted">
              或直接访问 <Link href="/contact">/contact</Link>
            </Badge>
          </div>
          <div className="muted">建议：联系时提供公司名称、联系人、需求（周报/导出/订阅规模）。</div>
        </CardContent>
      </Card>

      <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
        <Button type="button" variant="secondary" onClick={onLater} disabled={marking || auth.loading || !auth.user}>
          稍后再看，进入系统
        </Button>
      </div>
    </div>
  );
}
