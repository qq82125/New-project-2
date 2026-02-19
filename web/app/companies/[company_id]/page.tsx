import Link from 'next/link';

import SignalCard from '../../../components/signal/SignalCard';
import { EmptyState, ErrorState } from '../../../components/States';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../../components/ui/card';
import { Badge } from '../../../components/ui/badge';
import { ApiHttpError } from '../../../lib/api/client';
import { getRegistrationsList } from '../../../lib/api/analytics';
import {
  getCompany,
  getCompanyHighRiskRegistrations,
  getCompanyNewTracks,
  getCompanyTrajectory,
  type CompanyTrajectoryPoint,
} from '../../../lib/api/companies';
import { getCompanySignal } from '../../../lib/api/signals';
import type { SignalResponse } from '../../../lib/api/types';

function formatError(err: unknown): string {
  if (err instanceof Error && err.message) return err.message;
  return '未知错误';
}

function isNotFound(err: unknown): boolean {
  return err instanceof ApiHttpError && err.status === 404;
}

function monthKey(date: Date): string {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  return `${y}-${m}`;
}

function buildLast24Months(): string[] {
  const now = new Date();
  const out: string[] = [];
  for (let i = 23; i >= 0; i -= 1) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
    out.push(monthKey(d));
  }
  return out;
}

function fillTrajectory24(series: CompanyTrajectoryPoint[]): CompanyTrajectoryPoint[] {
  const byMonth = new Map<string, CompanyTrajectoryPoint>();
  series.forEach((p) => {
    if (p.month) byMonth.set(p.month, p);
  });

  return buildLast24Months().map((m) => {
    const p = byMonth.get(m);
    if (p) {
      return {
        month: m,
        total: Number(p.total || 0),
        new_count: Number(p.new_count || 0),
        cancel_count: Number(p.cancel_count || 0),
        net_change: Number(p.net_change || 0),
      };
    }
    return { month: m, total: 0, new_count: 0, cancel_count: 0, net_change: 0 };
  });
}

function normalizeSignal(signal: SignalResponse): SignalResponse {
  const orderedNames = ['new_registrations_12m', 'new_tracks_12m', 'growth_slope'];
  return {
    ...signal,
    factors: [...(signal.factors || [])]
      .map((f) => ({ ...f, explanation: f.explanation || '暂无说明' }))
      .sort((a, b) => {
        const ia = orderedNames.indexOf(a.name);
        const ib = orderedNames.indexOf(b.name);
        const va = ia === -1 ? Number.MAX_SAFE_INTEGER : ia;
        const vb = ib === -1 ? Number.MAX_SAFE_INTEGER : ib;
        return va - vb;
      }),
  };
}

export default async function CompanyDetailPage({ params }: { params: Promise<{ company_id: string }> }) {
  const { company_id } = await params;
  const [companyResult, signalResult, trajectoryResult, newTracksResult, highRiskResult, fallbackRegsResult] = await Promise.allSettled([
    getCompany(company_id),
    getCompanySignal(company_id),
    getCompanyTrajectory(company_id, '24m'),
    getCompanyNewTracks(company_id, '24m'),
    getCompanyHighRiskRegistrations(company_id, '12m'),
    getRegistrationsList({ company: company_id, page: 1, page_size: 5 }),
  ]);

  const companyNotFound = companyResult.status === 'rejected' && isNotFound(companyResult.reason);
  const signalNotFound = signalResult.status === 'rejected' && isNotFound(signalResult.reason);
  const trajectoryNotFound = trajectoryResult.status === 'rejected' && isNotFound(trajectoryResult.reason);
  const newTracksNotFound = newTracksResult.status === 'rejected' && isNotFound(newTracksResult.reason);
  const highRiskNotFound = highRiskResult.status === 'rejected' && isNotFound(highRiskResult.reason);

  const company = companyResult.status === 'fulfilled' ? companyResult.value : null;
  const signal = signalResult.status === 'fulfilled' ? normalizeSignal(signalResult.value) : null;
  const trajectory = trajectoryResult.status === 'fulfilled' ? fillTrajectory24(trajectoryResult.value.series || []) : fillTrajectory24([]);
  const newTracks = newTracksResult.status === 'fulfilled' ? newTracksResult.value.items : [];
  const highRisk = highRiskResult.status === 'fulfilled' ? highRiskResult.value.items : [];
  const fallbackRegs = fallbackRegsResult.status === 'fulfilled' ? fallbackRegsResult.value.items : [];

  const groupedNewTracks = newTracks.reduce<Record<string, Array<{ track_id: string; track_name: string }>>>((acc, item) => {
    if (!acc[item.month]) acc[item.month] = [];
    acc[item.month].push({ track_id: item.track_id, track_name: item.track_name });
    return acc;
  }, {});
  const groupedMonths = Object.keys(groupedNewTracks).sort((a, b) => b.localeCompare(a));

  return (
    <div className="grid">
      <Card>
        <CardHeader>
          <CardTitle>企业摘要</CardTitle>
          <CardDescription>企业当前规模与覆盖范围。</CardDescription>
        </CardHeader>
        <CardContent className="grid">
          {companyResult.status === 'rejected' && !companyNotFound ? <ErrorState text={`企业摘要加载失败：${formatError(companyResult.reason)}`} /> : null}
          {!company ? (
            <EmptyState text="暂无企业摘要数据" />
          ) : (
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
              <Badge variant="muted">公司: {company.company_name}</Badge>
              <Badge variant="muted">origin: {company.origin || '-'}</Badge>
              <Badge variant="muted">当前注册证: {company.current_registrations ?? 0}</Badge>
              <Badge variant="muted">当前赛道: {company.current_tracks ?? 0}</Badge>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>扩张强度指数</CardTitle>
          <CardDescription>company growth（可解释因子）。</CardDescription>
        </CardHeader>
        <CardContent className="grid">
          {signalResult.status === 'rejected' && !signalNotFound ? <ErrorState text={`扩张强度指数加载失败：${formatError(signalResult.reason)}`} /> : null}
          {signal ? <SignalCard title="Company Growth" signal={signal} /> : <EmptyState text="暂无扩张强度指数数据" />}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>月度轨迹（24m）</CardTitle>
          <CardDescription>缺失月份已补 0，共 24 行。</CardDescription>
        </CardHeader>
        <CardContent className="grid">
          {trajectoryResult.status === 'rejected' && !trajectoryNotFound ? <ErrorState text={`轨迹加载失败：${formatError(trajectoryResult.reason)}`} /> : null}
          <div style={{ overflowX: 'auto' }}>
            <table className="ui-table">
              <thead>
                <tr>
                  <th>month</th>
                  <th>total</th>
                  <th>new_count</th>
                  <th>cancel_count</th>
                  <th>net_change</th>
                </tr>
              </thead>
              <tbody>
                {trajectory.map((row) => (
                  <tr key={row.month}>
                    <td>{row.month}</td>
                    <td>{row.total}</td>
                    <td>{row.new_count}</td>
                    <td>{row.cancel_count}</td>
                    <td>{row.net_change}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>新赛道进入记录</CardTitle>
          <CardDescription>按月份分组，可下钻赛道页。</CardDescription>
        </CardHeader>
        <CardContent className="grid">
          {newTracksResult.status === 'rejected' && !newTracksNotFound ? <ErrorState text={`新赛道记录加载失败：${formatError(newTracksResult.reason)}`} /> : null}
          {groupedMonths.length === 0 ? (
            <div className="grid">
              <EmptyState text="暂无新赛道进入记录" />
              <div className="card">
                <div className="muted">可先从以下入口继续探索：</div>
                <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
                  <Link href={`/analytics/time-slice?mode=window&window=24m&company=${encodeURIComponent(company?.company_name || company_id)}`}>
                    查看 24m 时间切片
                  </Link>
                  <Link href={`/search?company=${encodeURIComponent(company?.company_name || company_id)}`}>查看该企业搜索结果</Link>
                  <Link href="/companies/tracking">查看企业维度追踪</Link>
                </div>
              </div>
            </div>
          ) : (
            groupedMonths.map((month) => (
              <div key={month} className="card">
                <div className="muted">{month}</div>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
                  {groupedNewTracks[month].map((t) => (
                    <Link key={`${month}-${t.track_id}`} href={`/tracks/${encodeURIComponent(t.track_id)}`}>
                      {t.track_name}
                    </Link>
                  ))}
                </div>
              </div>
            ))
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>高风险证清单</CardTitle>
          <CardDescription>可下钻注册证详情。</CardDescription>
        </CardHeader>
        <CardContent>
          {highRiskResult.status === 'rejected' && !highRiskNotFound ? <ErrorState text={`高风险证加载失败：${formatError(highRiskResult.reason)}`} /> : null}
          {highRisk.length === 0 ? (
            <div className="grid">
              <EmptyState text="暂无高风险证" />
              {fallbackRegs.length > 0 ? (
                <div className="card">
                  <div className="muted">该企业最近注册证（兜底推荐）</div>
                  <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
                    {fallbackRegs.map((r) => (
                      <Link key={r.registration_no} href={`/registrations/${encodeURIComponent(r.registration_no)}`}>
                        {r.registration_no}
                      </Link>
                    ))}
                  </div>
                </div>
              ) : (
                <div className="card">
                  <div className="muted">暂无可推荐注册证，可先查看：</div>
                  <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
                    <Link href={`/search?company=${encodeURIComponent(company?.company_name || company_id)}`}>该企业搜索结果</Link>
                    <Link href={`/analytics/time-slice?mode=window&window=12m&company=${encodeURIComponent(company?.company_name || company_id)}`}>
                      12m 时间切片
                    </Link>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table className="ui-table">
                <thead>
                  <tr>
                    <th>registration_no</th>
                    <th>company</th>
                    <th>expiry_date</th>
                    <th>level</th>
                  </tr>
                </thead>
                <tbody>
                  {highRisk.map((row) => (
                    <tr key={row.registration_no}>
                      <td>
                        <Link href={`/registrations/${encodeURIComponent(row.registration_no)}`}>{row.registration_no}</Link>
                      </td>
                      <td>{row.company || company?.company_name || '-'}</td>
                      <td>{row.expiry_date || '-'}</td>
                      <td>{row.level || '-'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
