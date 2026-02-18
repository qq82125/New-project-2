import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../../components/ui/card';
import { Badge } from '../../../components/ui/badge';
import { EmptyState, ErrorState } from '../../../components/States';
import { adminFetchJson } from '../../../lib/admin';
import { ADMIN_TEXT } from '../../../constants/admin-i18n';
import { LRI_RISK_ZH, labelFrom } from '../../../constants/display';
import Link from 'next/link';

type AdminLriItem = {
  registration_id: string;
  registration_no: string;
  product_id?: string | null;
  product_name?: string | null;
  ivd_category?: string | null;
  methodology_code?: string | null;
  methodology_name_cn?: string | null;
  tte_days?: number | null;
  renewal_count: number;
  competitive_count: number;
  gp_new_12m: number;
  lri_norm: number;
  risk_level: string;
  model_version: string;
  calculated_at: string;
};

type AdminLriResp = {
  total: number;
  items: AdminLriItem[];
};

export const dynamic = 'force-dynamic';

function riskVariant(level: string): 'success' | 'warning' | 'danger' | 'muted' {
  const v = String(level || '').toUpperCase();
  if (v === 'LOW') return 'success';
  if (v === 'MID') return 'warning';
  if (v === 'HIGH') return 'danger';
  if (v === 'CRITICAL') return 'danger';
  return 'muted';
}

export default async function AdminLriPage({
  searchParams,
}: {
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
}) {
  const sp = (await searchParams) || {};
  const view = String(sp.view || 'high'); // high | all | lowmid
  let data: AdminLriResp | null = null;
  let error: string | null = null;
  try {
    data = await adminFetchJson<AdminLriResp>('/api/admin/lri?limit=500&offset=0');
  } catch (e) {
    error = e instanceof Error ? e.message : '加载失败';
  }

  const allItems = data?.items || [];
  const total = Number(data?.total || 0);
  const dist = allItems.reduce<Record<string, number>>((acc, it) => {
    const k = String(it.risk_level || '').toUpperCase() || 'UNKNOWN';
    acc[k] = (acc[k] || 0) + 1;
    return acc;
  }, {});

  const items =
    view === 'all'
      ? allItems
      : view === 'lowmid'
        ? allItems.filter((x) => !['HIGH', 'CRITICAL'].includes(String(x.risk_level || '').toUpperCase()))
        : allItems.filter((x) => ['HIGH', 'CRITICAL'].includes(String(x.risk_level || '').toUpperCase()));

  return (
    <div className="grid">
      <Card>
        <CardHeader>
          <CardTitle>{ADMIN_TEXT.modules.lri.title}</CardTitle>
          <CardDescription>{ADMIN_TEXT.modules.lri.description}</CardDescription>
        </CardHeader>
        <CardContent style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
          <Badge variant="muted">视图: {view === 'all' ? '全部' : view === 'lowmid' ? '低/中风险' : '高风险'}</Badge>
          <Badge variant="muted">样本: {items.length} / {Math.min(allItems.length, total)}</Badge>
          {Object.entries(dist).map(([k, v]) => (
            <Badge key={k} variant={riskVariant(k)}>
              {labelFrom(LRI_RISK_ZH, k)}: {v}
            </Badge>
          ))}
          <span className="muted">· 默认只看高风险；每个注册证号取最新一条 LRI 结果。</span>
          <span className="muted">·</span>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
            <Link href="/admin/lri?view=high" className={`ui-btn ui-btn--sm ${view === 'high' ? '' : 'ui-btn--secondary'}`}>
              高风险
            </Link>
            <Link href="/admin/lri?view=all" className={`ui-btn ui-btn--sm ${view === 'all' ? '' : 'ui-btn--secondary'}`}>
              全部
            </Link>
            <Link
              href="/admin/lri?view=lowmid"
              className={`ui-btn ui-btn--sm ${view === 'lowmid' ? '' : 'ui-btn--secondary'}`}
            >
              低/中风险
            </Link>
          </div>
        </CardContent>
      </Card>

      {error ? <ErrorState text={`LRI 加载失败：${error}`} /> : null}

      {!error && items.length === 0 ? <EmptyState text="暂无 LRI 数据（可先运行 lri-compute 计算）。" /> : null}

      {!error && items.length > 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>高风险清单</CardTitle>
            <CardDescription>按计算时间倒序。点击注册证号可复制用于检索。</CardDescription>
          </CardHeader>
          <CardContent>
            <table className="table">
              <thead>
                <tr>
                  <th>注册证号</th>
                  <th>产品</th>
                  <th>方法学</th>
                  <th>风险</th>
                  <th>分数</th>
                  <th>TTE</th>
                  <th>RH</th>
                  <th>CD</th>
                  <th>GP</th>
                  <th>时间</th>
                </tr>
              </thead>
              <tbody>
                {items.map((it) => {
                  const risk = String(it.risk_level || '').toUpperCase();
                  const pct = Number(it.lri_norm || 0) * 100;
                  return (
                    <tr key={`${it.registration_id}:${it.calculated_at}`}>
                      <td style={{ fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace' }}>
                        {it.registration_no || '-'}
                      </td>
                      <td title={it.product_name || ''}>{it.product_name || '-'}</td>
                      <td>{it.methodology_name_cn || it.methodology_code || '-'}</td>
                      <td>
                        <Badge variant={riskVariant(risk)}>{labelFrom(LRI_RISK_ZH, risk)}</Badge>
                      </td>
                      <td>{pct.toFixed(1)}%</td>
                      <td>{it.tte_days ?? '-'}</td>
                      <td>{it.renewal_count ?? 0}</td>
                      <td>{it.competitive_count ?? 0}</td>
                      <td>{it.gp_new_12m ?? 0}</td>
                      <td className="muted">{String(it.calculated_at || '').slice(0, 19).replace('T', ' ')}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}
