import Link from 'next/link';
import SignalCard from '../../../components/signal/SignalCard';
import VersionChainTimeline from '../../../components/timeline/VersionChainTimeline';
import { EmptyState, ErrorState } from '../../../components/States';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../../components/ui/card';
import { Badge } from '../../../components/ui/badge';
import { STATUS_ZH, labelFrom } from '../../../constants/display';
import PackagingTree, { type PackingEdge } from '../../../components/udi/PackagingTree';
import { getRegistration, getRegistrationSnapshot, getRegistrationTimeline } from '../../../lib/api/registrations';
import { getRegistrationSignal } from '../../../lib/api/signals';
import type { SignalResponse, TimelineEvent } from '../../../lib/api/types';
import { ApiHttpError } from '../../../lib/api/client';

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

function renderSnapshotKeyFields(snapshot: unknown) {
  if (!snapshot || typeof snapshot !== 'object' || Array.isArray(snapshot)) return null;

  const data = snapshot as Record<string, unknown>;
  const keys: Array<{ key: string; label: string }> = [
    { key: 'registration_no', label: '注册证号' },
    { key: 'company', label: '公司' },
    { key: 'track', label: '赛道' },
    { key: 'status', label: '状态' },
    { key: 'expiry_date', label: '有效期至' },
  ];

  const items = keys.filter((k) => data[k.key] !== undefined && data[k.key] !== null && data[k.key] !== '');
  if (items.length === 0) return null;

  return (
    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
      {items.map((item) => (
        <Badge key={item.key} variant="muted">
          {item.label}: {String(data[item.key])}
        </Badge>
      ))}
    </div>
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
      <Card>
        <CardHeader>
          <CardTitle>注册证摘要</CardTitle>
          <CardDescription>注册证基础信息与状态摘要。</CardDescription>
        </CardHeader>
        <CardContent className="grid">
          {registrationResult.status === 'rejected' && !registrationNotFound ? (
            <ErrorState text={`注册证加载失败：${formatError(registrationResult.reason)}`} />
          ) : null}
          {!registration ? (
            <EmptyState text="注册证不存在或暂无摘要数据" />
          ) : (
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
              <Badge variant="muted">注册证号: {registration.registration_no}</Badge>
              <Badge variant="muted">公司: {registration.company || '-'}</Badge>
              <Badge variant="muted">赛道: {registration.track || '-'}</Badge>
              <Badge variant="muted">状态: {labelFrom(STATUS_ZH, registration.status || '') || registration.status || '-'}</Badge>
              <Badge variant="muted">有效期至: {registration.expiry_date || '-'}</Badge>
              <Badge variant="muted">境内: {registration.is_domestic === undefined || registration.is_domestic === null ? '-' : registration.is_domestic ? '是' : '否'}</Badge>
              <Badge variant="muted">DI 数量: {registration.di_count ?? variants.length}</Badge>
            </div>
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
            <ErrorState text={`生命周期指数加载失败：${formatError(signalResult.reason)}`} />
          ) : null}
          {orderedSignal ? <SignalCard title="Registration Lifecycle" signal={orderedSignal} /> : <EmptyState text="暂无生命周期指数数据" />}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>版本链时间轴</CardTitle>
          <CardDescription>按事件序列只读展示（create/change/renew/cancel）。</CardDescription>
        </CardHeader>
        <CardContent className="grid">
          {timelineResult.status === 'rejected' && !timelineNotFound ? (
            <ErrorState text={`版本链加载失败：${formatError(timelineResult.reason)}`} />
          ) : null}
          {timeline.length === 0 ? <EmptyState text="暂无版本链事件" /> : <VersionChainTimeline events={timeline as TimelineEvent[]} />}
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

          {atRaw && !at ? <ErrorState text="快照月份格式应为 YYYY-MM" /> : null}
          {at && snapshotResult.status === 'rejected' && !snapshotNotFound ? (
            <ErrorState text={`快照加载失败：${formatError(snapshotResult.reason)}`} />
          ) : null}

          {at && snapshotResult.status === 'fulfilled' ? (
            !snapshot || (typeof snapshot === 'object' && !Array.isArray(snapshot) && Object.keys(snapshot as Record<string, unknown>).length === 0) ? (
              <EmptyState text="该月份无快照" />
            ) : (
              <div className="grid">
                {renderSnapshotKeyFields(snapshot)}
                <details>
                  <summary>查看原始 JSON</summary>
                  <pre style={{ overflow: 'auto', marginTop: 8 }}>{JSON.stringify(snapshot, null, 2)}</pre>
                </details>
              </div>
            )
          ) : null}
          {at && snapshotNotFound ? <EmptyState text="该月份无快照" /> : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>注册证详情</CardTitle>
          <CardDescription>以 registration_no 为唯一锚点，汇总规格（UDI-DI）与包装层级。</CardDescription>
        </CardHeader>
        <CardContent className="grid">
          {!registration ? (
            <EmptyState text="暂无注册证详情" />
          ) : (
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
              <Badge variant="muted">注册证号: {registration.registration_no}</Badge>
              <Badge variant="muted">备案号: {registration.filing_no || '-'}</Badge>
              <Badge variant="muted">批准日期: {registration.approval_date || '-'}</Badge>
              <Badge variant="muted">有效期至: {registration.expiry_date || '-'}</Badge>
              <Badge variant="muted">状态: {labelFrom(STATUS_ZH, registration.status || '') || registration.status || '-'}</Badge>
              {registration.is_stub && registration.source_hint === 'UDI' && registration.verified_by_nmpa === false ? (
                <Badge variant="warning">UDI来源｜待核验</Badge>
              ) : null}
            </div>
          )}
          <div>
            <Link href={`/search?reg_no=${encodeURIComponent(registration?.registration_no || registration_no)}`}>按该注册证号搜索产品</Link>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>UDI 规格（DI）</CardTitle>
          <CardDescription>一个注册证可对应多个 DI；包装层级来自 UDI packingList（可用于按包装维度对齐报价/集采目录）。</CardDescription>
        </CardHeader>
        <CardContent className="grid">
          {variants.length === 0 ? (
            <EmptyState text="暂无 DI 规格记录（可先运行 udi:variants 生成绑定）" />
          ) : (
            variants.slice(0, 200).map((it) => {
              const packings = packingsFromPackagingJson(it.packaging_json) as PackingEdge[];
              return (
                <div key={it.di} className="card">
                  <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
                    <Badge variant="muted">DI: {it.di}</Badge>
                    {it.model_spec ? <Badge variant="muted">型号/货号: {it.model_spec}</Badge> : null}
                    {it.manufacturer ? <Badge variant="muted">注册人: {it.manufacturer}</Badge> : null}
                    {it.evidence_raw_document_id ? (
                      <Badge variant="muted">证据: {String(it.evidence_raw_document_id).slice(0, 8)}…</Badge>
                    ) : null}
                  </div>
                  {packings.length === 0 ? (
                    <div style={{ marginTop: 8 }}>
                      <PackagingTree packings={[]} />
                    </div>
                  ) : (
                    <div style={{ marginTop: 10 }} className="grid">
                      <div className="muted">包装层级</div>
                      <PackagingTree packings={packings} />
                    </div>
                  )}
                </div>
              );
            })
          )}
        </CardContent>
      </Card>
    </div>
  );
}
