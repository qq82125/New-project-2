import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../../components/ui/card';
import ContactInfoManager from '../../../components/admin/ContactInfoManager';

import { adminFetchJson } from '../../../lib/admin';
import { ADMIN_TEXT } from '../../../constants/admin-i18n';

type AdminConfigItem = { config_key: string; config_value: any; updated_at: string };
type AdminConfigsResp = { code: number; message: string; data: { items: AdminConfigItem[] } };

export const dynamic = 'force-dynamic';

async function getContactConfig(): Promise<AdminConfigItem | null> {
  const body = await adminFetchJson<AdminConfigsResp['data']>('/api/admin/configs');
  const items = body?.items || [];
  return items.find((x) => x.config_key === 'public_contact_info') || null;
}

export default async function AdminContactPage() {
  const cfg = await getContactConfig();

  return (
    <div className="grid">
      <Card>
        <CardHeader>
          <CardTitle>{ADMIN_TEXT.modules.contact.title}</CardTitle>
          <CardDescription>{ADMIN_TEXT.modules.contact.description}</CardDescription>
        </CardHeader>
        <CardContent>
          <span className="muted">建议与“用户与会员”模块联动维护，确保联系方式与开通流程口径一致。</span>
        </CardContent>
      </Card>

      <ContactInfoManager initialConfig={cfg} />
    </div>
  );
}
