import { getAdminMe } from '../../lib/admin';
import AdminWorkspaceShell from '../../components/admin/AdminWorkspaceShell';

export const dynamic = 'force-dynamic';

export default async function AdminLayout({ children }: { children: React.ReactNode }) {
  const me = await getAdminMe();
  const mode = String(process.env.PENDING_QUEUE_MODE || 'document_only').toLowerCase();
  const pendingQueueMode = (mode === 'both' || mode === 'record_only' || mode === 'document_only' ? mode : 'document_only') as
    | 'both'
    | 'document_only'
    | 'record_only';
  return (
    <AdminWorkspaceShell me={me} pendingQueueMode={pendingQueueMode}>
      {children}
    </AdminWorkspaceShell>
  );
}
