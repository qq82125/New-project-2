import Link from 'next/link';
import SignalCard from '../../../components/signal/SignalCard';
import { EmptyState, ErrorState } from '../../../components/States';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../../components/ui/card';
import { Badge } from '../../../components/ui/badge';
import { STATUS_ZH, labelFrom } from '../../../constants/display';
import PackagingTree, { type PackingEdge } from '../../../components/udi/PackagingTree';
import CopyTextButton from '../../../components/detail/CopyTextButton';
import { getRegistration, getRegistrationSnapshot, getRegistrationTimeline } from '../../../lib/api/registrations';
import { getRegistrationSignal } from '../../../lib/api/signals';
import type { SignalResponse, TimelineEvent } from '../../../lib/api/types';
import { ApiHttpError } from '../../../lib/api/client';
import { toChangeRows, toEvidenceRows } from '../../../lib/detail';

function packingsFromPackagingJson(v: any): any[] {
  if (!v) return [];
  if (Array.isArray(v)) return v;
  if (typeof v === 'object' && Array.isArray((v as any).packings)) return (v as any).packings;
  return [];
}

function formatError(err: unknown): string {
  if (err instanceof Error && err.message) return err.message;
  return '未知错误';
}

function isNotFound(err: unknown): boolean {
  return err instanceof ApiHttpError && err.status === 404;
}

function normalizeSignal(signal: SignalResponse): SignalResponse {
  return {
    ...signal,
    factors: (signal.factors || []).map((f) => ({
      ...f,
      explanation: f.explanation || '暂无说明',
    })),
  };
}

function viewText(v: unknown): string {
  if (v === null || v === undefined || v === '') return '-';
  if (typeof v === 'string') return v;
  if (typeof v === 'number' || typeof v === 'boolean') return String(v);
  try {
    return JSON.stringify(v);
  } catch {
    return String(v);
  }
}

function FieldRow({ label, value }: { label: string; value: unknown }) {
  const text = viewText(value);
  const isLong = text.length > 120;
  return (
    <div className="columns-2" style={{ gap: 8 }}>
      <div className="muted">{label}</div>
      <div>
        {isLong ? (
          <details>
            <summary>show more</summary>
            <div style={{ whiteSpace: 'pre-wrap', marginTop: 6 }}>{text}</div>
          </details>
        ) : (
          <span>{text}</span>
        )}
      </div>
    </div>
  );
}

function FieldGroup({ title, rows }: { title: string; rows: Array<{ label: string; value: unknown }> }) {
  return (
    <details className="card" open>
      <summary style={{ cursor: 'pointer', fontWeight: 700 }}>{title}</summary>
      <div className="grid" style={{ marginTop: 10 }}>
        {rows.map((row) => (
          <FieldRow key={row.label} label={row.label} value={row.value} />
        ))}
      </div>
    </details>
  );
}

export default async function RegistrationDetailPage({
  params,
  searchParams,
}: {
  params: Promise<{ registration_no: string }>;
  searchParams?: Promise<{ at?: string }>;
}) {
  const emptySearch: { at?: string } = {};
  const [{ registration_no }, sp] = await Promise.all([params, searchParams ?? Promise.resolve(emptySearch)]);
  const atRaw = typeof sp.at === 'string' ? sp.at.trim() : '';
  const at = /^\d{4}-(0[1-9]|1[0-2])$/.test(atRaw) ? atRaw : '';

  const [registrationResult, signalResult, timelineResult, snapshotResult] = await Promise.allSettled([
    getRegistration(registration_no),
    getRegistrationSignal(registration_no),
    getRegistrationTimeline(registration_no),
    at ? getRegistrationSnapshot(registration_no, at) : Promise.resolve(null),
  ]);

  const registrationNotFound = registrationResult.status === 'rejected' && isNotFound(registrationResult.reason);
  const signalNotFound = signalResult.status === 'rejected' && isNotFound(signalResult.reason);
  const timelineNotFound = timelineResult.status === 'rejected' && isNotFound(timelineResult.reason);
  const snapshotNotFound = snapshotResult.status === 'rejected' && isNotFound(snapshotResult.reason);
  const registration = registrationResult.status === 'fulfilled' ? registrationResult.value : null;
  const signal = signalResult.status === 'fulfilled' ? normalizeSignal(signalResult.value) : null;
  const timeline = timelineResult.status === 'fulfilled' ? timelineResult.value : [];
  const snapshot = snapshotResult.status === 'fulfilled' ? snapshotResult.value : null;
  const variants = registration?.variants || [];

  const latestChangeDate = timeline.length > 0 ? String(timeline[0].observed_at || '-') : '-';
  const evidenceRows = toEvidenceRows(timeline as TimelineEvent[]);
  const changeRows = toChangeRows(timeline as TimelineEvent[]).slice(0, 5);

  const requiredFactorOrder = ['days_to_expiry', 'has_renewal_history', 'competition_density'];
  const orderedSignal = signal
    ? {
        ...signal,
        factors: [...signal.factors].sort((a, b) => {
          const ia = requiredFactorOrder.indexOf(a.name);
          const ib = requiredFactorOrder.indexOf(b.name);
          const va = ia === -1 ? Number.MAX_SAFE_INTEGER : ia;
          const vb = ib === -1 ? Number.MAX_SAFE_INTEGER : ib;
          return va - vb;
        }),
      }
    : null;

  return (
    <div className="grid">
      <Card data-testid="detail__overview__panel">
        <CardHeader>
          <CardTitle>产品详情</CardTitle>
          <CardDescription>概览区</CardDescription>
        </CardHeader>
        <CardContent className="grid">
          {registrationResult.status === 'rejected' && !registrationNotFound ? (
            <ErrorState text={`加载失败，请重试（${formatError(registrationResult.reason)}）`} />
          ) : null}
          {!registration ? (
            <EmptyState text="暂无数据" />
          ) : (
            <>
              <div>
                <Link
                  className="ui-btn ui-btn--sm ui-btn--secondary"
                  href={`/search?reg_no=${encodeURIComponent(registration.registration_no || registration_no)}`}
                  data-testid="detail__header__back"
                >
                  返回
                </Link>
              </div>
              <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
                <Badge variant="muted">注册证名称: {registration.track || registration.registration_no}</Badge>
                <Badge variant="muted">企业名: {registration.company || '-'}</Badge>
                <Badge variant="muted">状态: {labelFrom(STATUS_ZH, registration.status || '') || registration.status || '-'}</Badge>
              </div>
              <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }} data-testid="detail__overview__registration_no">
                <Badge variant="muted">注册证号: {registration.registration_no}</Badge>
                <CopyTextButton value={registration.registration_no} />
              </div>
              <div className="columns-3">
                <div>
                  <div className="muted">批准日期</div>
                  <div>{registration.approval_date || '-'}</div>
                </div>
                <div>
                  <div className="muted">变更日期</div>
                  <div>{latestChangeDate}</div>
                </div>
                <div>
                  <div className="muted">失效日期</div>
                  <div>{registration.expiry_date || '-'}</div>
                </div>
              </div>
            </>
          )}
        </CardContent>
      </Card>

      <Card data-testid="detail__fields__panel">
        <CardHeader>
          <CardTitle>结构化字段</CardTitle>
          <CardDescription>字段分组折叠展示</CardDescription>
        </CardHeader>
        <CardContent className="grid">
          {!registration ? (
            <EmptyState text="暂无数据" />
          ) : (
            <>
              <FieldGroup
                title="基本信息"
                rows={[
                  { label: '注册证号', value: registration.registration_no },
                  { label: '企业名', value: registration.company },
                  { label: '状态', value: labelFrom(STATUS_ZH, registration.status || '') || registration.status },
                  { label: '备案号', value: registration.filing_no },
                ]}
              />
              <FieldGroup
                title="适用范围"
                rows={[
                  { label: '赛道', value: registration.track },
                  { label: '境内', value: registration.is_domestic == null ? '-' : registration.is_domestic ? '是' : '否' },
                  { label: 'DI数量', value: registration.di_count ?? variants.length },
                ]}
              />
              <FieldGroup
                title="结构组成"
                rows={[
                  { label: 'DI列表', value: variants.length ? variants.map((x) => x.di).join(' / ') : '-' },
                  { label: '首个型号/货号', value: variants[0]?.model_spec || '-' },
                  { label: '首个注册人', value: variants[0]?.manufacturer || '-' },
                ]}
              />
            </>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>证据与变更</CardTitle>
          <CardDescription>可解释证据链与最近字段变更</CardDescription>
        </CardHeader>
        <CardContent className="grid">
          {timelineResult.status === 'rejected' && !timelineNotFound ? (
            <ErrorState text={`加载失败，请重试（${formatError(timelineResult.reason)}）`} />
          ) : (
            <>
              <div className="card" data-testid="detail__evidence__panel">
                <div style={{ fontWeight: 700, marginBottom: 8 }}>证据</div>
                {evidenceRows.length === 0 ? (
                  <EmptyState text="暂无可追溯证据（优先补采 raw_documents）" />
                ) : (
                  <div className="grid">
                    {evidenceRows.slice(0, 8).map((item, idx) => (
                      <div key={`${item.source}-${idx}`} className="card">
                        <div><span className="muted">来源：</span>{item.source || '-'}</div>
                        <div><span className="muted">观察时间：</span>{item.observed_at || '-'}</div>
                        <div>
                          <span className="muted">证据片段：</span>
                          {item.excerpt.length > 120 ? (
                            <details>
                              <summary>show more</summary>
                              <div style={{ whiteSpace: 'pre-wrap', marginTop: 6 }}>{item.excerpt}</div>
                            </details>
                          ) : (
                            <span>{item.excerpt || '-'}</span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div className="card" data-testid="detail__timeline__panel">
                <div style={{ fontWeight: 700, marginBottom: 8 }}>变更</div>
                {changeRows.length === 0 ? (
                  <EmptyState text="暂无字段变更记录" />
                ) : (
                  <div className="grid">
                    {changeRows.map((row, idx) => (
                      <div key={`${row.field}-${idx}`} className="columns-2" style={{ gap: 8 }}>
                        <div><span className="muted">字段：</span>{row.field}</div>
                        <div><span className="muted">时间：</span>{row.observed_at}</div>
                        <div><span className="muted">旧值：</span>{row.old_value}</div>
                        <div><span className="muted">新值：</span>{row.new_value}</div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>生命周期指数</CardTitle>
          <CardDescription>registration lifecycle（可解释因子）。</CardDescription>
        </CardHeader>
        <CardContent className="grid">
          {signalResult.status === 'rejected' && !signalNotFound ? (
            <ErrorState text={`加载失败，请重试（${formatError(signalResult.reason)}）`} />
          ) : null}
          {orderedSignal ? <SignalCard title="Registration Lifecycle" signal={orderedSignal} /> : <EmptyState text="暂无数据" />}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>快照回放</CardTitle>
          <CardDescription>输入 at=YYYY-MM 查看该月份快照。</CardDescription>
        </CardHeader>
        <CardContent className="grid">
          <form method="get" style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
            <input name="at" type="month" defaultValue={atRaw} style={{ minWidth: 180 }} />
            <button type="submit">回放</button>
          </form>

          {atRaw && !at ? <ErrorState text="加载失败，请重试" /> : null}
          {at && snapshotResult.status === 'rejected' && !snapshotNotFound ? <ErrorState text="加载失败，请重试" /> : null}

          {at && snapshotResult.status === 'fulfilled' ? (
            !snapshot || (typeof snapshot === 'object' && !Array.isArray(snapshot) && Object.keys(snapshot as Record<string, unknown>).length === 0) ? (
              <EmptyState text="暂无数据" />
            ) : (
              <div className="grid">
                <details>
                  <summary>show more</summary>
                  <pre style={{ overflow: 'auto', marginTop: 8 }}>{JSON.stringify(snapshot, null, 2)}</pre>
                </details>
              </div>
            )
          ) : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>UDI 规格（DI）</CardTitle>
          <CardDescription>一个注册证可对应多个 DI。</CardDescription>
        </CardHeader>
        <CardContent className="grid">
          {variants.length === 0 ? (
            <EmptyState text="暂无数据" />
          ) : (
            variants.slice(0, 200).map((it) => {
              const packings = packingsFromPackagingJson(it.packaging_json) as PackingEdge[];
              return (
                <div key={it.di} className="card">
                  <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
                    <Badge variant="muted">DI: {it.di}</Badge>
                    {it.model_spec ? <Badge variant="muted">型号/货号: {it.model_spec}</Badge> : null}
                    {it.manufacturer ? <Badge variant="muted">注册人: {it.manufacturer}</Badge> : null}
                  </div>
                  <div style={{ marginTop: 10 }} className="grid">
                    <PackagingTree packings={packings} />
                  </div>
                </div>
              );
            })
          )}
          <div>
            <Link href={`/search?reg_no=${encodeURIComponent(registration?.registration_no || registration_no)}`}>返回搜索结果</Link>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
