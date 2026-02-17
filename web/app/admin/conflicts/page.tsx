import ConflictsQueueManager from '../../../components/admin/ConflictsQueueManager';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../../components/ui/card';

import { adminFetchJson } from '../../../lib/admin';
import { ADMIN_TEXT } from '../../../constants/admin-i18n';

type ConflictItem = {
  id: string;
  registration_no: string;
  registration_id?: string | null;
  field_name: string;
  candidates: Array<{ source_key?: string; value?: string; observed_at?: string }>;
  status: string;
  winner_value?: string | null;
  winner_source_key?: string | null;
  source_run_id?: number | null;
  resolved_by?: string | null;
  resolved_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};
type ConflictsResp = {
  code: number;
  message: string;
  data: { items: ConflictItem[]; count: number; status: string };
};

export const dynamic = 'force-dynamic';

async function getConflicts(): Promise<ConflictItem[]> {
  const data = await adminFetchJson<ConflictsResp['data']>('/api/admin/conflicts?status=open&limit=200');
  return data?.items || [];
}

export default async function AdminConflictsPage() {
  const items = await getConflicts();
  return (
    <div className="grid">
      <Card>
        <CardHeader>
          <CardTitle>{ADMIN_TEXT.modules.conflicts.title}</CardTitle>
          <CardDescription>{ADMIN_TEXT.modules.conflicts.description}</CardDescription>
        </CardHeader>
        <CardContent>
          <span className="muted">支持按注册证聚合查看冲突，人工裁决后写入可追溯审计链。</span>
        </CardContent>
      </Card>

      <ConflictsQueueManager initialItems={items} />
    </div>
  );
}
