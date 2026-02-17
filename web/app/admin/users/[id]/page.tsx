import Link from 'next/link';
import { notFound } from 'next/navigation';

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../../../components/ui/card';
import AdminUserDetail from '../../../../components/admin/users/AdminUserDetail';
import { ADMIN_TEXT } from '../../../../constants/admin-i18n';

export const dynamic = 'force-dynamic';

export default async function AdminUserDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const userId = Number(id);
  if (!Number.isFinite(userId) || userId <= 0) notFound();

  return (
    <div className="grid">
      <Card>
        <CardHeader>
          <CardTitle>{ADMIN_TEXT.modules.userDetail.title}</CardTitle>
          <CardDescription>{ADMIN_TEXT.modules.userDetail.description}</CardDescription>
        </CardHeader>
        <CardContent style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
          <span className="muted">建议操作前先核对邮箱、套餐状态和生效时间。</span>
          <span className="muted">·</span>
          <Link href="/admin/users" className="muted">
            返回用户列表
          </Link>
        </CardContent>
      </Card>

      <AdminUserDetail userId={userId} />
    </div>
  );
}
