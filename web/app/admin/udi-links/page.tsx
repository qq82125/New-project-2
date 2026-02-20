import UdiPendingLinksManager from '../../../components/admin/UdiPendingLinksManager';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../../components/ui/card';
import { adminFetchJson } from '../../../lib/admin';
import { ADMIN_TEXT } from '../../../constants/admin-i18n';
type PendingItem = {
  id: string;
  di: string;
  status: string;
  reason: string;
  reason_code?: string | null;
  match_reason?: string | null;
  confidence?: number;
  reversible?: boolean;
  linked_by?: string | null;
  candidate_company_name?: string | null;
  candidate_product_name?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};
type PendingResp = {
  code: number;
  message: string;
  data: { items: PendingItem[]; count: number; status: string };
};

export const dynamic = 'force-dynamic';

async function getPendingItems(): Promise<PendingItem[]> {
  const body = await adminFetchJson<PendingResp['data']>('/api/admin/udi/pending-links?status=PENDING&limit=200');
  return body?.items || [];
}

export default async function AdminUdiLinksPage() {
  const items = await getPendingItems();
  return (
    <div className="grid">
      <Card>
        <CardHeader>
          <CardTitle>{ADMIN_TEXT.modules.udiLinks.title}</CardTitle>
          <CardDescription>{ADMIN_TEXT.modules.udiLinks.description}</CardDescription>
        </CardHeader>
        <CardContent>
          <span className="muted">支持筛选、手动绑定与结果回写，便于持续清理 UDI 映射积压。</span>
        </CardContent>
      </Card>

      <UdiPendingLinksManager initialItems={items} />
    </div>
  );
}
