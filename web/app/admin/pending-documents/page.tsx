import PendingDocumentsManager from '../../../components/admin/PendingDocumentsManager';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../../components/ui/card';

import { adminFetchJson } from '../../../lib/admin';
import { ADMIN_TEXT } from '../../../constants/admin-i18n';

type PendingDocItem = {
  id: string;
  raw_document_id: string;
  source_run_id?: number | null;
  reason_code: string;
  status: string;
  created_at?: string | null;
  updated_at?: string | null;
};

type PendingDocResp = {
  code: number;
  message: string;
  data: { items: PendingDocItem[]; count: number; total?: number };
};

export const dynamic = 'force-dynamic';

async function getPendingDocsInitial(): Promise<{ items: PendingDocItem[]; total: number }> {
  const body = await adminFetchJson<PendingDocResp['data']>(
    '/api/admin/pending-documents?status=pending&limit=50&offset=0&order_by=created_at%20desc'
  );
  return {
    items: body?.items || [],
    total: Number(body?.total ?? body?.count ?? 0),
  };
}

export default async function AdminPendingDocumentsPage() {
  const initial = await getPendingDocsInitial();
  return (
    <div className="grid">
      <Card>
        <CardHeader>
          <CardTitle>{ADMIN_TEXT.modules.pendingDocuments.title}</CardTitle>
          <CardDescription>{ADMIN_TEXT.modules.pendingDocuments.description}</CardDescription>
        </CardHeader>
        <CardContent>
          <span className="muted">
            该队列按 raw_documents 维度积压。补齐注册证号后会触发一次标准入库（先 upsert registrations，再写衍生实体）。
          </span>
        </CardContent>
      </Card>

      <PendingDocumentsManager initialItems={initial.items} initialTotal={initial.total} />
    </div>
  );
}

