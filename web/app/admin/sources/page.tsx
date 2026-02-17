import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../../components/ui/card';
import SourcesRegistryManager from '../../../components/admin/SourcesRegistryManager';
import { adminFetchJson } from '../../../lib/admin';
import { ADMIN_TEXT } from '../../../constants/admin-i18n';

type SourceItem = {
  source_key: string;
  display_name: string;
  entity_scope: string;
  default_evidence_grade: string;
  parser_key: string;
  enabled_by_default: boolean;
  config: {
    id?: string | null;
    enabled?: boolean;
    schedule_cron?: string | null;
    fetch_params?: Record<string, unknown>;
    parse_params?: Record<string, unknown>;
    upsert_policy?: Record<string, unknown>;
    last_run_at?: string | null;
    last_status?: string | null;
    last_error?: string | null;
    created_at?: string | null;
    updated_at?: string | null;
  };
};

export const dynamic = 'force-dynamic';

export default async function AdminSourcesPage() {
  const data = await adminFetchJson<{ items: SourceItem[]; count: number }>('/api/admin/sources');
  return (
    <div className="grid">
      <Card>
        <CardHeader>
          <CardTitle>{ADMIN_TEXT.modules.sources.title}</CardTitle>
          <CardDescription>{ADMIN_TEXT.modules.sources.description}</CardDescription>
        </CardHeader>
        <CardContent>
          <span className="muted">保存后会立即刷新列表，错误会展示后端返回的 code/message。</span>
        </CardContent>
      </Card>

      <SourcesRegistryManager initialItems={data.items || []} />
    </div>
  );
}
