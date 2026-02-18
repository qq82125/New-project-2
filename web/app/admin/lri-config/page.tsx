import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../../components/ui/card';
import { adminFetchJson } from '../../../lib/admin';
import { ADMIN_TEXT } from '../../../constants/admin-i18n';
import LriModelConfigManager from '../../../components/admin/LriModelConfigManager';

type AdminConfigItem = {
  config_key: string;
  config_value: any;
  updated_at: string;
};

type AdminConfigsResp = {
  code: number;
  message: string;
  data: { items: AdminConfigItem[] };
};

export const dynamic = 'force-dynamic';

async function getLriConfig(): Promise<AdminConfigItem | null> {
  const body = await adminFetchJson<AdminConfigsResp['data']>('/api/admin/configs');
  const items = body?.items || [];
  return items.find((x) => x.config_key === 'lri_v1_config') || null;
}

export default async function AdminLriConfigPage() {
  const cfg = await getLriConfig();
  return (
    <div className="grid">
      <Card>
        <CardHeader>
          <CardTitle>{ADMIN_TEXT.modules.lriConfig.title}</CardTitle>
          <CardDescription>{ADMIN_TEXT.modules.lriConfig.description}</CardDescription>
        </CardHeader>
        <CardContent>
          <span className="muted">
            保存后立即生效（后续计算将使用新阈值）。建议保存后点击“一键重算”做一次样本对比验证。
          </span>
        </CardContent>
      </Card>

      <LriModelConfigManager initialConfig={cfg} />
    </div>
  );
}

