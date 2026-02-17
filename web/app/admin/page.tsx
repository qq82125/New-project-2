import Link from 'next/link';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card';
import { Badge } from '../../components/ui/badge';
import { adminFetch, adminFetchJson } from '../../lib/admin';
import { ADMIN_TEXT } from '../../constants/admin-i18n';
import { cn } from '../../components/ui/cn';

type AdminStats = {
  total_ivd_products: number;
  rejected_total: number;
  by_ivd_category: Array<{ key: string; value: number }>;
  by_source: Array<{ key: string; value: number }>;
};
type PendingStats = {
  by_source_key: Array<{ source_key: string; open: number; resolved: number; ignored: number }>;
  by_reason_code: Array<{ reason_code: string; open: number }>;
  backlog: {
    open_total: number;
    resolved_last_24h: number;
    resolved_last_7d: number;
    windows: { resolved_24h_hours: number; resolved_7d_days: number };
  };
};
type CountResp = { count?: number; total?: number };

export const dynamic = 'force-dynamic';

function fmtInt(n: number): string {
  try {
    return Number(n || 0).toLocaleString('zh-CN');
  } catch {
    return String(n || 0);
  }
}

function severityFromCount(n: number): 'success' | 'warning' | 'danger' {
  if (n <= 0) return 'success';
  if (n <= 50) return 'warning';
  return 'danger';
}

export default async function AdminHomePage() {
  const [statsData, pendingStats, conflictsCount, udiPendingCount] = await Promise.all([
    adminFetchJson<AdminStats>('/api/admin/stats?limit=20').catch(() => null),
    adminFetchJson<PendingStats>('/api/admin/pending/stats').catch(() => null),
    adminFetchJson<CountResp>('/api/admin/conflicts?status=open&limit=1').catch(() => null),
    (async () => {
      const res = await adminFetch('/api/admin/udi/pending-links?status=PENDING&limit=1', { allowNotOk: true });
      if (!res.ok) return null;
      const body = (await res.json().catch(() => null)) as { code?: number; data?: CountResp } | null;
      if (!body || Number(body.code) !== 0) return null;
      return body.data || null;
    })(),
  ]);
  const pendingOpen = Number(pendingStats?.backlog?.open_total || 0);
  const conflictsOpen = Number(conflictsCount?.count ?? conflictsCount?.total ?? 0);
  const udiOpen = Number(udiPendingCount?.count ?? udiPendingCount?.total ?? 0);

  return (
    <div className="grid admin-home">
      <Card className="admin-hero">
        <CardHeader>
          <CardTitle>{ADMIN_TEXT.modules.home.title}</CardTitle>
          <CardDescription>{ADMIN_TEXT.modules.home.description}</CardDescription>
        </CardHeader>
        <CardContent className="admin-hero__content">
          <div className="admin-hero__kpis">
            <Link href="/admin/pending" className={cn('admin-kpi-card', pendingOpen > 0 ? 'is-warn' : 'is-ok')}>
              <div className="admin-kpi-card__label">待处理记录</div>
              <div className="admin-kpi-card__value">{fmtInt(pendingOpen)}</div>
              <div className="admin-kpi-card__meta">
                <Badge variant={severityFromCount(pendingOpen)}>建议优先处理</Badge>
                <span className="muted">注册锚点缺失积压</span>
              </div>
            </Link>
            <Link href="/admin/udi-links" className={cn('admin-kpi-card', udiOpen > 0 ? 'is-warn' : 'is-ok')}>
              <div className="admin-kpi-card__label">UDI 待映射</div>
              <div className="admin-kpi-card__value">{fmtInt(udiOpen)}</div>
              <div className="admin-kpi-card__meta">
                <Badge variant={severityFromCount(udiOpen)}>建议每日清理</Badge>
                <span className="muted">DI 到注册证号绑定</span>
              </div>
            </Link>
            <Link href="/admin/conflicts" className={cn('admin-kpi-card', conflictsOpen > 0 ? 'is-risk' : 'is-ok')}>
              <div className="admin-kpi-card__label">冲突待裁决</div>
              <div className="admin-kpi-card__value">{fmtInt(conflictsOpen)}</div>
              <div className="admin-kpi-card__meta">
                <Badge variant={severityFromCount(conflictsOpen)}>需填写原因</Badge>
                <span className="muted">字段级冲突队列</span>
              </div>
            </Link>
          </div>
          <div className="admin-hero__tips">
            <Badge variant="warning">流程建议：先补齐锚点，再做冲突裁决</Badge>
            <Badge variant="muted">配置建议：先灰度低频源，再推广主源</Badge>
            <Badge variant="muted">口径：仅影响后台展示，不改后端接口</Badge>
          </div>
        </CardContent>
      </Card>

      <section className="admin-home__grid">
        <Card>
          <CardHeader>
            <CardTitle>今日工作流</CardTitle>
            <CardDescription>把 backlog 变成可消化的日常动作</CardDescription>
          </CardHeader>
          <CardContent className="admin-flow">
            <div className="admin-flow__item">
              <div className="admin-flow__idx">1</div>
              <div className="admin-flow__body">
                <div className="admin-flow__title">处理待处理记录</div>
                <div className="muted">补齐 registration_no，降低 registration_id 缺失率</div>
              </div>
              <Link className="ui-btn ui-btn--secondary" href="/admin/pending">进入</Link>
            </div>
            <div className="admin-flow__item">
              <div className="admin-flow__idx">2</div>
              <div className="admin-flow__body">
                <div className="admin-flow__title">清理 UDI 待映射</div>
                <div className="muted">把 DI 挂到注册证号下，提升规格覆盖</div>
              </div>
              <Link className="ui-btn ui-btn--secondary" href="/admin/udi-links">进入</Link>
            </div>
            <div className="admin-flow__item">
              <div className="admin-flow__idx">3</div>
              <div className="admin-flow__body">
                <div className="admin-flow__title">裁决冲突队列</div>
                <div className="muted">人工裁决需填写原因，确保审计可追溯</div>
              </div>
              <Link className="ui-btn ui-btn--secondary" href="/admin/conflicts">进入</Link>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>运维入口</CardTitle>
            <CardDescription>低风险配置优先</CardDescription>
          </CardHeader>
          <CardContent className="grid" style={{ gap: 8 }}>
            <Link href="/admin/sources" className="ui-btn ui-btn--secondary">数据源配置</Link>
            <Link href="/admin/users" className="ui-btn ui-btn--secondary">用户与会员</Link>
            <Link href="/admin/contact" className="ui-btn ui-btn--secondary">联系信息</Link>
          </CardContent>
        </Card>
      </section>

      <Card>
        <CardHeader>
          <CardTitle>数据概览与健康</CardTitle>
          <CardDescription>库存结构 + 待处理来源/原因（用于定位解析缺陷）</CardDescription>
        </CardHeader>
        <CardContent className="grid" style={{ gap: 12 }}>
          {!statsData ? (
            <div className="muted">库存概览加载失败或暂无数据</div>
          ) : (
            <div className="admin-health__top">
              <div className="admin-health__metric">
                <div className="muted">IVD 总数</div>
                <div className="admin-health__metric-value">{fmtInt(statsData.total_ivd_products)}</div>
              </div>
              <div className="admin-health__metric">
                <div className="muted">拒收记录</div>
                <div className="admin-health__metric-value">{fmtInt(statsData.rejected_total)}</div>
              </div>
              <div className="admin-health__chips">
                {(statsData.by_ivd_category || []).slice(0, 8).map((x) => (
                  <Badge key={`cat-${x.key}`} variant="muted">
                    {x.key}: {x.value}
                  </Badge>
                ))}
              </div>
            </div>
          )}

          <div className="columns-2" style={{ gap: 12 }}>
            <div>
              <div className="muted" style={{ marginBottom: 6 }}>待处理来源 TOP</div>
              {!pendingStats ? (
                <div className="muted">待处理统计加载失败或暂无数据</div>
              ) : (
                <div className="grid" style={{ gap: 6 }}>
                  {(pendingStats.by_source_key || []).slice(0, 8).map((x) => (
                    <div key={`src-${x.source_key}`} className="admin-mini-row">
                      <span className="admin-mini-row__k">{x.source_key}</span>
                      <span className="admin-mini-row__v">待处理 {x.open} / 已解决 {x.resolved}</span>
                      <Link className="muted admin-mini-row__a" href={`/admin/data-sources?source_key=${encodeURIComponent(x.source_key)}`}>查看</Link>
                    </div>
                  ))}
                </div>
              )}
            </div>
            <div>
              <div className="muted" style={{ marginBottom: 6 }}>待处理原因码 TOP</div>
              {!pendingStats ? (
                <div className="muted">待处理统计加载失败或暂无数据</div>
              ) : (
                <div className="grid" style={{ gap: 6 }}>
                  {(pendingStats.by_reason_code || []).slice(0, 10).map((x) => (
                    <div key={`rsn-${x.reason_code}`} className="admin-mini-row">
                      <span className="admin-mini-row__k">{x.reason_code || '（空）'}</span>
                      <span className="admin-mini-row__v">待处理 {x.open}</span>
                      <span className="admin-mini-row__a muted">定位解析缺陷</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
