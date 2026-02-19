import Link from 'next/link';

import { Badge } from '../../../components/ui/badge';
import { Button } from '../../../components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../../components/ui/card';
import { Input } from '../../../components/ui/input';
import { Select } from '../../../components/ui/select';
import { EmptyState, ErrorState } from '../../../components/States';
import PaginationControls from '../../../components/PaginationControls';
import { getRegistrationsList, getTimeSliceMetrics, type RegistrationListItem, type TimeSliceMetrics, type TimeSliceWindow } from '../../../lib/api/analytics';
import { ApiHttpError } from '../../../lib/api/client';

type PageParams = {
  mode?: 'at' | 'window';
  at?: string;
  window?: string;
  track?: string;
  company?: string;
  category?: string;
  origin?: string;
  status?: string;
  page?: string;
  page_size?: string;
};

const WINDOW_OPTIONS: TimeSliceWindow[] = ['3m', '6m', '12m', '24m'];

function isMonth(value: string | undefined): value is string {
  return !!value && /^\d{4}-(0[1-9]|1[0-2])$/.test(value);
}

function formatError(err: unknown): string {
  if (err instanceof Error && err.message) return err.message;
  return '未知错误';
}

function isNotFound(err: unknown): boolean {
  return err instanceof ApiHttpError && err.status === 404;
}

function metricValue(value: number | null | undefined): string {
  if (value === null || value === undefined) return '--';
  return String(value);
}

function metricsCard(
  title: string,
  value: number | null | undefined,
  description: string,
) {
  return (
    <Card>
      <CardContent className="grid">
        <div className="muted">{title}</div>
        <div style={{ fontSize: 28, fontWeight: 700 }}>{metricValue(value)}</div>
        <div className="muted">{description}</div>
      </CardContent>
    </Card>
  );
}

export default async function TimeSliceAnalyticsPage({ searchParams }: { searchParams: Promise<PageParams> }) {
  const params = await searchParams;
  const mode = params.mode === 'at' ? 'at' : 'window';
  const at = isMonth(params.at) ? params.at : '';
  const windowValue = WINDOW_OPTIONS.includes(params.window as TimeSliceWindow) ? (params.window as TimeSliceWindow) : '12m';
  const currentMonth = new Date().toISOString().slice(0, 7);
  const atValue = at || currentMonth;

  const page = Math.max(1, Number(params.page || '1'));
  const pageSize = Math.max(1, Number(params.page_size || '20'));

  const filters = {
    track: params.track?.trim() || '',
    company: params.company?.trim() || '',
    category: params.category?.trim() || '',
    origin: params.origin?.trim() || '',
    status: params.status?.trim() || '',
  };

  const metricsQuery = mode === 'at'
    ? { at: atValue }
    : { window: windowValue };

  const [metricsResult, listResult] = await Promise.allSettled([
    getTimeSliceMetrics(metricsQuery, filters),
    getRegistrationsList({ ...filters, page, page_size: pageSize }),
  ]);

  const metricsNotFound = metricsResult.status === 'rejected' && isNotFound(metricsResult.reason);
  const listNotFound = listResult.status === 'rejected' && isNotFound(listResult.reason);
  const metrics = metricsResult.status === 'fulfilled' ? metricsResult.value : null;
  const list = listResult.status === 'fulfilled' ? listResult.value : null;

  return (
    <div className="grid">
      <Card>
        <CardHeader>
          <CardTitle>时间切片分析</CardTitle>
          <CardDescription>统一查看时点库存（at）与滚动区间变化（window）。</CardDescription>
        </CardHeader>
        <CardContent className="grid">
          <form className="controls" method="GET">
            <Input name="track" defaultValue={filters.track} placeholder="赛道 track" />
            <Input name="company" defaultValue={filters.company} placeholder="公司 company" />
            <Input name="category" defaultValue={filters.category} placeholder="分类 category" />
            <Input name="origin" defaultValue={filters.origin} placeholder="来源 origin" />
            <Input name="status" defaultValue={filters.status} placeholder="状态 status" />

            <Select name="mode" defaultValue={mode}>
              <option value="window">window（滚动）</option>
              <option value="at">at（时点）</option>
            </Select>

            <Input name="at" type="month" defaultValue={atValue} />
            <Select name="window" defaultValue={windowValue}>
              {WINDOW_OPTIONS.map((w) => (
                <option key={w} value={w}>
                  {w}
                </option>
              ))}
            </Select>

            <Input name="page_size" defaultValue={String(pageSize)} inputMode="numeric" placeholder="每页数量" />
            <Button type="submit">刷新</Button>
          </form>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
            <Badge variant="muted">模式: {mode === 'at' ? 'at' : 'window'}</Badge>
            {mode === 'at' ? <Badge variant="muted">at={metricsQuery.at}</Badge> : <Badge variant="muted">window={metricsQuery.window}</Badge>}
          </div>
        </CardContent>
      </Card>

      {metricsResult.status === 'rejected' && !metricsNotFound ? (
        <ErrorState text={`指标加载失败：${formatError(metricsResult.reason)}`} />
      ) : (
        <div className="columns-4">
          {metricsCard('库存 stock_count', (metrics as TimeSliceMetrics | null)?.stock_count, '时点库存，或区间口径下可选返回')}
          {metricsCard('新增 new_count', (metrics as TimeSliceMetrics | null)?.new_count, '滚动区间新增')}
          {metricsCard('注销 cancel_count', (metrics as TimeSliceMetrics | null)?.cancel_count, '滚动区间注销')}
          {metricsCard('延期 renew_count', (metrics as TimeSliceMetrics | null)?.renew_count, '滚动区间延期/续期')}
        </div>
      )}

      <Card>
        <CardHeader>
          <CardTitle>下钻列表</CardTitle>
          <CardDescription>点击注册证号进入详情页。</CardDescription>
        </CardHeader>
        <CardContent className="grid">
          {listResult.status === 'rejected' && !listNotFound ? (
            <ErrorState text={`列表加载失败：${formatError(listResult.reason)}`} />
          ) : !list || list.items.length === 0 ? (
            <EmptyState text="暂无列表数据" />
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table className="ui-table">
                <thead>
                  <tr>
                    <th>注册证号</th>
                    <th>公司</th>
                    <th>赛道</th>
                    <th>状态</th>
                    <th>有效期至</th>
                  </tr>
                </thead>
                <tbody>
                  {list.items.map((item: RegistrationListItem) => (
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
                          {item.track || '-'}
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

          {list ? (
            <PaginationControls
              basePath="/analytics/time-slice"
              params={{
                mode,
                at: atValue,
                window: windowValue,
                track: filters.track,
                company: filters.company,
                category: filters.category,
                origin: filters.origin,
                status: filters.status,
              }}
              page={page}
              pageSize={pageSize}
              total={list.total}
            />
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}
