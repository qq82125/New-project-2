import Link from 'next/link';

import { EmptyState, ErrorState } from '../../../components/States';
import SignalCard from '../../../components/signal/SignalCard';
import PaginationControls from '../../../components/PaginationControls';
import { Badge } from '../../../components/ui/badge';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../../components/ui/card';
import { ApiHttpError } from '../../../lib/api/client';
import { getTrackSignal } from '../../../lib/api/signals';
import { getTrack, getTrackRegistrations, getTrackStats, type TrackRegistrationItem } from '../../../lib/api/tracks';
import type { SignalResponse } from '../../../lib/api/types';

type PageSearchParams = {
  page?: string;
  page_size?: string;
};

function formatError(err: unknown): string {
  if (err instanceof Error && err.message) return err.message;
  return '未知错误';
}

function isNotFound(err: unknown): boolean {
  return err instanceof ApiHttpError && err.status === 404;
}

function normalizeSignal(signal: SignalResponse): SignalResponse {
  const orderedNames = ['total_count', 'new_rate_12m', 'domestic_ratio'];
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

export default async function TrackDetailPage({
  params,
  searchParams,
}: {
  params: Promise<{ track_id: string }>;
  searchParams: Promise<PageSearchParams>;
}) {
  const [{ track_id }, sp] = await Promise.all([params, searchParams]);
  const page = Math.max(1, Number(sp.page || '1'));
  const pageSize = Math.max(1, Number(sp.page_size || '20'));

  const [trackResult, signalResult, statsResult, registrationsResult] = await Promise.allSettled([
    getTrack(track_id),
    getTrackSignal(track_id),
    getTrackStats(track_id, '12m'),
    getTrackRegistrations(track_id, page, pageSize),
  ]);

  const trackNotFound = trackResult.status === 'rejected' && isNotFound(trackResult.reason);
  const signalNotFound = signalResult.status === 'rejected' && isNotFound(signalResult.reason);
  const statsNotFound = statsResult.status === 'rejected' && isNotFound(statsResult.reason);
  const registrationsNotFound = registrationsResult.status === 'rejected' && isNotFound(registrationsResult.reason);

  const track = trackResult.status === 'fulfilled' ? trackResult.value : null;
  const signal = signalResult.status === 'fulfilled' ? normalizeSignal(signalResult.value) : null;
  const stats = statsResult.status === 'fulfilled' ? statsResult.value : null;
  const registrations = registrationsResult.status === 'fulfilled' ? registrationsResult.value : null;

  return (
    <div className="grid">
      <Card>
        <CardHeader>
          <CardTitle>赛道信息</CardTitle>
          <CardDescription>赛道头信息。</CardDescription>
        </CardHeader>
        <CardContent className="grid">
          {trackResult.status === 'rejected' && !trackNotFound ? <ErrorState text={`赛道信息加载失败：${formatError(trackResult.reason)}`} /> : null}
          {!track ? (
            <EmptyState text="暂无赛道信息" />
          ) : (
            <div className="grid">
              <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
                <Badge variant="muted">track_id: {track.track_id}</Badge>
                <Badge variant="muted">track_name: {track.track_name}</Badge>
              </div>
              <div className="muted">{track.description || '暂无赛道描述'}</div>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>竞争密度指数</CardTitle>
          <CardDescription>track competition（可解释因子）。</CardDescription>
        </CardHeader>
        <CardContent className="grid">
          {signalResult.status === 'rejected' && !signalNotFound ? <ErrorState text={`竞争密度指数加载失败：${formatError(signalResult.reason)}`} /> : null}
          {signal ? <SignalCard title="Track Competition" signal={signal} /> : <EmptyState text="暂无竞争密度指数数据" />}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>12m 新增趋势</CardTitle>
          <CardDescription>按月展示新增证数量。</CardDescription>
        </CardHeader>
        <CardContent className="grid">
          {statsResult.status === 'rejected' && !statsNotFound ? <ErrorState text={`趋势加载失败：${formatError(statsResult.reason)}`} /> : null}
          {!stats || stats.series.length === 0 ? (
            <EmptyState text="暂无趋势数据" />
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table className="ui-table">
                <thead>
                  <tr>
                    <th>month</th>
                    <th>new_count</th>
                  </tr>
                </thead>
                <tbody>
                  {stats.series.map((point) => (
                    <tr key={point.month}>
                      <td>{point.month}</td>
                      <td>{point.new_count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>同类证列表</CardTitle>
          <CardDescription>点击任意列进入注册证页。</CardDescription>
        </CardHeader>
        <CardContent className="grid">
          {registrationsResult.status === 'rejected' && !registrationsNotFound ? (
            <ErrorState text={`同类证列表加载失败：${formatError(registrationsResult.reason)}`} />
          ) : !registrations || registrations.items.length === 0 ? (
            <EmptyState text="暂无同类证数据" />
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table className="ui-table">
                <thead>
                  <tr>
                    <th>registration_no</th>
                    <th>company</th>
                    <th>status</th>
                    <th>expiry_date</th>
                  </tr>
                </thead>
                <tbody>
                  {registrations.items.map((item: TrackRegistrationItem) => (
                    <tr key={item.registration_no}>
                      <td>
                        <Link href={`/registrations/${encodeURIComponent(item.registration_no)}`} className="block">
                          {item.registration_no}
                        </Link>
                      </td>
                      <td>
                        <Link href={`/registrations/${encodeURIComponent(item.registration_no)}`} className="block">
                          {item.company || '-'}
                        </Link>
                      </td>
                      <td>
                        <Link href={`/registrations/${encodeURIComponent(item.registration_no)}`} className="block">
                          {item.status || '-'}
                        </Link>
                      </td>
                      <td>
                        <Link href={`/registrations/${encodeURIComponent(item.registration_no)}`} className="block">
                          {item.expiry_date || '-'}
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {registrations ? (
            <PaginationControls
              basePath={`/tracks/${encodeURIComponent(track_id)}`}
              params={{}}
              page={page}
              pageSize={pageSize}
              total={registrations.total}
            />
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}
