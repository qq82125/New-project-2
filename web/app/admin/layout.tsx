import { getAdminMe } from '../../lib/admin';
import AdminWorkspaceShell from '../../components/admin/AdminWorkspaceShell';

export const dynamic = 'force-dynamic';

export default async function AdminLayout({ children }: { children: React.ReactNode }) {
  const me = await getAdminMe();
  return <AdminWorkspaceShell me={me}>{children}</AdminWorkspaceShell>;
}

