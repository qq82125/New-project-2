import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../../components/ui/card';
import AdminUsersManager from '../../../components/admin/users/AdminUsersManager';
import { ADMIN_TEXT } from '../../../constants/admin-i18n';

export const dynamic = 'force-dynamic';

export default async function AdminUsersPage() {
  return (
    <div className="grid">
      <Card>
        <CardHeader>
          <CardTitle>{ADMIN_TEXT.modules.users.title}</CardTitle>
          <CardDescription>{ADMIN_TEXT.modules.users.description}</CardDescription>
        </CardHeader>
        <CardContent>
          <span className="muted">建议先筛选目标用户，再执行会员变更，避免误操作。</span>
        </CardContent>
      </Card>

      <AdminUsersManager />
    </div>
  );
}
