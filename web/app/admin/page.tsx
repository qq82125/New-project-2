import Link from 'next/link';
import { Suspense } from 'react';
import { Badge } from '../../components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card';
import { cn } from '../../components/ui/cn';
import { Skeleton } from '../../components/ui/skeleton';
import { ADMIN_TEXT } from '../../constants/admin-i18n';
import { adminFetchJson } from '../../lib/admin';
import { IVD_CATEGORY_ZH, LRI_RISK_ZH, labelFrom } from '../../constants/display';

type AdminStats = {
  total_ivd_products: number;
  rejected_total: number;
  by_ivd_category: Array<{ key: string; value: number }>;
  by_source: Array<{ key: string; value: number }>;
};
type PendingStats = {
  by_source_key: Array<{ source_key: string; pending: number; resolved: number; ignored: number }>;
  by_reason_code: Array<{ reason_code: string; pending: number }>;
  backlog: {
    pending_total: number;
    resolved_last_24h: number;
    resolved_last_7d: number;
    windows: { resolved_24h_hours: number; resolved_7d_days: number };
  };
};
type LriQuality = {
  metric_date?: string | null;
  pending_count: number;
  lri_computed_count: number;
  lri_missing_methodology_count: number;
  risk_level_distribution: Record<string, number>;
  updated_at?: string | null;
};
type HomeSummary = {
  pending_documents_pending_total: number;
  conflicts_open_total: number;
  udi_pending_total: number;
  lri_quality: LriQuality;
};

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

function AdminHeroSkeleton() {
  return (
    <Card className="admin-hero">
      <CardHeader>
        <CardTitle>{ADMIN_TEXT.modules.home.title}</CardTitle>
        <CardDescription>{ADMIN_TEXT.modules.home.description}</CardDescription>
      </CardHeader>
      <CardContent className="admin-hero__content">
        <div className="admin-hero__kpis">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={`kpi-skel-${i}`} className={cn('admin-kpi-card', 'is-ok')}>
              <Skeleton className="h-4 w-24" />
              <Skeleton className="h-10 w-28" />
              <Skeleton className="h-4 w-48" />
            </div>
          ))}
        </div>
        <div className="admin-hero__tips">
          <Skeleton className="h-6 w-64" />
          <Skeleton className="h-6 w-64" />
          <Skeleton className="h-6 w-64" />
        </div>
      </CardContent>
    </Card>
  );
}

async function AdminHeroCard() {
  const summary = await adminFetchJson<HomeSummary>('/api/admin/home-summary').catch(() => null);
  const pendingDocs = Number(summary?.pending_documents_pending_total || 0);
  const conflictsOpen = Number(summary?.conflicts_open_total || 0);
  const udiOpen = Number(summary?.udi_pending_total || 0);
  const lriDist = summary?.lri_quality?.risk_level_distribution || { LOW: 0, MID: 0, HIGH: 0, CRITICAL: 0 };

  return (
    <Card className="admin-hero">
      <CardHeader>
        <CardTitle>{ADMIN_TEXT.modules.home.title}</CardTitle>
        <CardDescription>{ADMIN_TEXT.modules.home.description}</CardDescription>
      </CardHeader>
      <CardContent className="admin-hero__content">
        <div className="admin-hero__kpis">
          <Link href="/admin/queue/pending-docs" className={cn('admin-kpi-card', pendingDocs > 0 ? 'is-warn' : 'is-ok')}>
            <div className="admin-kpi-card__label">待处理文档</div>
            <div className="admin-kpi-card__value">{fmtInt(pendingDocs)}</div>
            <div className="admin-kpi-card__meta">
              <Badge variant={severityFromCount(pendingDocs)}>建议优先处理</Badge>
              <span className="muted">缺 registration_no 的 raw_documents</span>
            </div>
          </Link>
          <Link href="/admin/queue/udi-pending" className={cn('admin-kpi-card', udiOpen > 0 ? 'is-warn' : 'is-ok')}>
            <div className="admin-kpi-card__label">UDI 待映射</div>
            <div className="admin-kpi-card__value">{fmtInt(udiOpen)}</div>
            <div className="admin-kpi-card__meta">
              <Badge variant={severityFromCount(udiOpen)}>建议每日清理</Badge>
              <span className="muted">DI 到注册证号绑定</span>
            </div>
          </Link>
          <Link href="/admin/queue/conflicts" className={cn('admin-kpi-card', conflictsOpen > 0 ? 'is-risk' : 'is-ok')}>
            <div className="admin-kpi-card__label">冲突待裁决</div>
            <div className="admin-kpi-card__value">{fmtInt(conflictsOpen)}</div>
            <div className="admin-kpi-card__meta">
              <Badge variant={severityFromCount(conflictsOpen)}>需填写原因</Badge>
              <span className="muted">字段级冲突队列</span>
            </div>
          </Link>
          <Link
            href="/admin/queue/high-risk"
            className={cn(
              'admin-kpi-card',
              Number(lriDist.HIGH || 0) + Number(lriDist.CRITICAL || 0) > 0 ? 'is-warn' : 'is-ok'
            )}
          >
            <div className="admin-kpi-card__label">LRI 高风险</div>
            <div className="admin-kpi-card__value">{fmtInt(Number(lriDist.HIGH || 0) + Number(lriDist.CRITICAL || 0))}</div>
            <div className="admin-kpi-card__meta">
              <Badge variant={severityFromCount(Number(lriDist.HIGH || 0) + Number(lriDist.CRITICAL || 0))}>每日关注</Badge>
              <span className="muted">HIGH+CRITICAL</span>
            </div>
          </Link>
        </div>
        <div className="admin-hero__tips">
          <Badge variant="warning">流程建议：先补齐锚点，再做冲突裁决</Badge>
          <Badge variant="muted">配置建议：先灰度低频源，再推广主源</Badge>
          <Badge variant="muted">口径：以“待处理文档队列”作为全局积压入口</Badge>
        </div>
      </CardContent>
    </Card>
  );
}

function AdminHealthSkeleton() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>数据概览与健康</CardTitle>
        <CardDescription>库存结构 + 待处理来源/原因（用于定位解析缺陷）</CardDescription>
      </CardHeader>
      <CardContent className="grid" style={{ gap: 12 }}>
        <Skeleton className="h-16 w-full" />
        <div className="columns-2" style={{ gap: 12 }}>
          <Skeleton className="h-40 w-full" />
          <Skeleton className="h-40 w-full" />
        </div>
        <Skeleton className="h-10 w-full" />
      </CardContent>
    </Card>
  );
}

async function AdminHealthCard() {
  const [statsData, pendingDocStats, lriQuality] = await Promise.all([
    adminFetchJson<AdminStats>('/api/admin/stats?limit=20').catch(() => null),
    adminFetchJson<PendingStats>('/api/admin/pending-documents/stats').catch(() => null),
    adminFetchJson<LriQuality>('/api/admin/lri/quality-latest').catch(() => null),
  ]);

  const lriDist = lriQuality?.risk_level_distribution || { LOW: 0, MID: 0, HIGH: 0, CRITICAL: 0 };

  return (
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
                  {labelFrom(IVD_CATEGORY_ZH, String(x.key || ''))}: {x.value}
                </Badge>
              ))}
            </div>
          </div>
        )}

        <div className="columns-2" style={{ gap: 12 }}>
          <div>
            <div className="muted" style={{ marginBottom: 6 }}>待处理来源 TOP</div>
            {!pendingDocStats ? (
              <div className="muted">待处理统计加载失败或暂无数据</div>
            ) : (
              <div className="grid" style={{ gap: 6 }}>
                {(pendingDocStats.by_source_key || []).slice(0, 8).map((x) => (
                  <div key={`src-${x.source_key}`} className="admin-mini-row">
                    <span className="admin-mini-row__k">{x.source_key}</span>
                    <span className="admin-mini-row__v">待处理 {x.pending} / 已解决 {x.resolved}</span>
                    <Link className="muted admin-mini-row__a" href={`/admin/data-sources?source_key=${encodeURIComponent(x.source_key)}`}>查看</Link>
                  </div>
                ))}
              </div>
            )}
          </div>
          <div>
            <div className="muted" style={{ marginBottom: 6 }}>待处理原因码 TOP</div>
            {!pendingDocStats ? (
              <div className="muted">待处理统计加载失败或暂无数据</div>
            ) : (
              <div className="grid" style={{ gap: 6 }}>
                {(pendingDocStats.by_reason_code || []).slice(0, 10).map((x) => (
                  <div key={`rsn-${x.reason_code}`} className="admin-mini-row">
                    <span className="admin-mini-row__k">{x.reason_code || '（空）'}</span>
                    <span className="admin-mini-row__v">待处理 {x.pending}</span>
                    <Link className="admin-mini-row__a" href={`/admin/reasons/${encodeURIComponent(x.reason_code || 'UNKNOWN')}`}>定位解析缺陷</Link>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        <div>
          <div className="muted" style={{ marginBottom: 6 }}>LRI 运行质量（每日指标）</div>
          {!lriQuality ? (
            <div className="muted">LRI 质量指标暂不可用（可能尚未跑过 lri-compute 或未迁移）。</div>
          ) : (
            <div className="admin-health__chips" style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
              <Badge variant="muted">日期: {String(lriQuality.metric_date || '-')}</Badge>
              <Badge variant="muted">待处理: {fmtInt(Number(lriQuality.pending_count || 0))}</Badge>
              <Badge variant="muted">已计算: {fmtInt(Number(lriQuality.lri_computed_count || 0))}</Badge>
              <Badge variant="muted">缺方法学: {fmtInt(Number(lriQuality.lri_missing_methodology_count || 0))}</Badge>
              <Badge variant="success">{labelFrom(LRI_RISK_ZH, 'LOW')} {fmtInt(Number(lriDist.LOW || 0))}</Badge>
              <Badge variant="warning">{labelFrom(LRI_RISK_ZH, 'MID')} {fmtInt(Number(lriDist.MID || 0))}</Badge>
              <Badge variant="danger">{labelFrom(LRI_RISK_ZH, 'HIGH')} {fmtInt(Number(lriDist.HIGH || 0))}</Badge>
              <Badge variant="danger">{labelFrom(LRI_RISK_ZH, 'CRITICAL')} {fmtInt(Number(lriDist.CRITICAL || 0))}</Badge>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

export default function AdminHomePage() {
  return (
    <div className="grid admin-home">
      <Suspense fallback={<AdminHeroSkeleton />}>
        <AdminHeroCard />
      </Suspense>

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
                <div className="admin-flow__title">处理待处理文档</div>
                <div className="muted">补齐 registration_no，并重放入库（先 registrations）</div>
              </div>
              <Link className="ui-btn ui-btn--secondary" href="/admin/queue/pending-docs">进入</Link>
            </div>
            <div className="admin-flow__item">
              <div className="admin-flow__idx">2</div>
              <div className="admin-flow__body">
                <div className="admin-flow__title">清理 UDI 待映射</div>
                <div className="muted">把 DI 挂到注册证号下，提升规格覆盖</div>
              </div>
              <Link className="ui-btn ui-btn--secondary" href="/admin/queue/udi-pending">进入</Link>
            </div>
            <div className="admin-flow__item">
              <div className="admin-flow__idx">3</div>
              <div className="admin-flow__body">
                <div className="admin-flow__title">裁决冲突队列</div>
                <div className="muted">人工裁决需填写原因，确保审计可追溯</div>
              </div>
              <Link className="ui-btn ui-btn--secondary" href="/admin/queue/conflicts">进入</Link>
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

      <Suspense fallback={<AdminHealthSkeleton />}>
        <AdminHealthCard />
      </Suspense>
    </div>
  );
}
