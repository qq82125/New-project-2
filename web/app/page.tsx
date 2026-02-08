import Link from 'next/link';
import { EmptyState, ErrorState } from '../components/States';
import { apiGet, qs } from '../lib/api';

type StatusData = {
  latest_runs: Array<{
    id: number;
    status: string;
    started_at: string;
    records_total: number;
    records_success: number;
    records_failed: number;
  }>;
};

type SummaryData = {
  start_date: string;
  end_date: string;
  total_new: number;
  total_updated: number;
  total_removed: number;
  latest_active_subscriptions: number;
};

type TrendData = {
  items: Array<{
    metric_date: string;
    new_products: number;
    updated_products: number;
    cancelled_products: number;
  }>;
};

type RankingsData = {
  top_new_days: Array<{ metric_date: string; value: number }>;
  top_removed_days: Array<{ metric_date: string; value: number }>;
};

type RadarData = {
  metric_date: string | null;
  items: Array<{ metric: string; value: number }>;
};

type SearchData = {
  items: Array<{
    product: {
      id: string;
      name: string;
      reg_no?: string | null;
      company?: { id: string; name: string } | null;
      expiry_date?: string | null;
    };
  }>;
};

function toCompanyRanking(items: SearchData['items']): Array<{ name: string; count: number }> {
  const map = new Map<string, number>();
  items.forEach((x) => {
    const name = x.product.company?.name;
    if (!name) return;
    map.set(name, (map.get(name) || 0) + 1);
  });
  return Array.from(map.entries())
    .map(([name, count]) => ({ name, count }))
    .sort((a, b) => b.count - a.count)
    .slice(0, 10);
}

export default async function DashboardPage() {
  const [statusRes, summaryRes, trendRes, rankingsRes, radarRes, newProductRes, expiringRes] = await Promise.all([
    apiGet<StatusData>('/api/status'),
    apiGet<SummaryData>('/api/dashboard/summary?days=30'),
    apiGet<TrendData>('/api/dashboard/trend?days=30'),
    apiGet<RankingsData>('/api/dashboard/rankings?days=30&limit=10'),
    apiGet<RadarData>('/api/dashboard/radar'),
    apiGet<SearchData>(`/api/search${qs({ page: 1, page_size: 20, sort_by: 'approved_date', sort_order: 'desc' })}`),
    apiGet<SearchData>(`/api/search${qs({ page: 1, page_size: 20, sort_by: 'expiry_date', sort_order: 'asc' })}`),
  ]);

  return (
    <div className="grid">
      <section className="card">
        <h2>IVD产品雷达</h2>
      </section>
      <section className="card">
        <h2>同步状态</h2>
        {statusRes.error ? (
          <ErrorState text={`状态加载失败：${statusRes.error}`} />
        ) : !statusRes.data || statusRes.data.latest_runs.length === 0 ? (
          <EmptyState text="暂无同步记录" />
        ) : (
          <div>
            最近一次：#{statusRes.data.latest_runs[0].id} {statusRes.data.latest_runs[0].status}，开始于{' '}
            {new Date(statusRes.data.latest_runs[0].started_at).toLocaleString()}
          </div>
        )}
      </section>

      <section className="kpis">
        {summaryRes.error || !summaryRes.data ? (
          <ErrorState text={`KPI 加载失败：${summaryRes.error || '未知错误'}`} />
        ) : (
          <>
            <div className="card"><div className="muted">30天新增</div><div className="kpi-value">{summaryRes.data.total_new}</div></div>
            <div className="card"><div className="muted">30天更新</div><div className="kpi-value">{summaryRes.data.total_updated}</div></div>
            <div className="card"><div className="muted">30天移除</div><div className="kpi-value">{summaryRes.data.total_removed}</div></div>
            <div className="card"><div className="muted">活跃订阅</div><div className="kpi-value">{summaryRes.data.latest_active_subscriptions}</div></div>
          </>
        )}
      </section>

      <section className="card">
        <h2>新增趋势（30天）</h2>
        {trendRes.error ? (
          <ErrorState text={`趋势加载失败：${trendRes.error}`} />
        ) : !trendRes.data || trendRes.data.items.length === 0 ? (
          <EmptyState text="暂无趋势数据" />
        ) : (
          <div className="spark">
            {trendRes.data.items.slice(-10).map((item) => (
              <div key={item.metric_date} className="spark-row">
                <span>{item.metric_date.slice(5)}</span>
                <div className="spark-bar" style={{ width: `${Math.max(6, item.new_products * 8)}px` }} />
                <span>{item.new_products}</span>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="columns-3">
        <div className="card">
          <h3>新增产品榜单</h3>
          {newProductRes.error ? (
            <ErrorState text={`加载失败：${newProductRes.error}`} />
          ) : !newProductRes.data || newProductRes.data.items.length === 0 ? (
            <EmptyState text="暂无新增产品" />
          ) : (
            <div className="list">
              {newProductRes.data.items.slice(0, 10).map((item) => (
                <div key={item.product.id} className="list-item">
                  <Link href={`/products/${item.product.id}`}>{item.product.name}</Link>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="card">
          <h3>企业榜单</h3>
          {newProductRes.error || !newProductRes.data ? (
            <ErrorState text={`加载失败：${newProductRes.error || '未知错误'}`} />
          ) : toCompanyRanking(newProductRes.data.items).length === 0 ? (
            <EmptyState text="暂无企业数据" />
          ) : (
            <div className="list">
              {toCompanyRanking(newProductRes.data.items).map((item) => (
                <div key={item.name} className="list-item">
                  <Link href={`/search${qs({ company: item.name })}`}>{item.name}</Link> ({item.count})
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="card">
          <h3>即将到期榜单</h3>
          {expiringRes.error ? (
            <ErrorState text={`加载失败：${expiringRes.error}`} />
          ) : !expiringRes.data || expiringRes.data.items.length === 0 ? (
            <EmptyState text="暂无到期数据" />
          ) : (
            <div className="list">
              {expiringRes.data.items.slice(0, 10).map((item) => (
                <div key={item.product.id} className="list-item">
                  <Link href={`/products/${item.product.id}`}>{item.product.name}</Link>
                  <div className="muted">{item.product.expiry_date || '-'}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      </section>

      <section className="columns-2">
        <div className="card">
          <h3>变更雷达列表</h3>
          {radarRes.error ? (
            <ErrorState text={`雷达加载失败：${radarRes.error}`} />
          ) : !radarRes.data || radarRes.data.items.length === 0 ? (
            <EmptyState text="暂无雷达数据" />
          ) : (
            <div className="list">
              {radarRes.data.items.map((item) => (
                <div key={item.metric} className="list-item">
                  <strong>{item.metric}</strong>: {item.value}
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="card">
          <h3>日榜（后端聚合）</h3>
          {rankingsRes.error ? (
            <ErrorState text={`榜单加载失败：${rankingsRes.error}`} />
          ) : !rankingsRes.data ? (
            <EmptyState text="暂无榜单" />
          ) : (
            <div className="columns-2">
              <div>
                <div className="muted">新增高峰日</div>
                <div className="list">
                  {rankingsRes.data.top_new_days.length === 0 ? (
                    <EmptyState text="暂无" />
                  ) : (
                    rankingsRes.data.top_new_days.map((x) => (
                      <div key={x.metric_date} className="list-item">
                        <Link href={`/search${qs({})}`}>{x.metric_date}</Link> / {x.value}
                      </div>
                    ))
                  )}
                </div>
              </div>
              <div>
                <div className="muted">移除高峰日</div>
                <div className="list">
                  {rankingsRes.data.top_removed_days.length === 0 ? (
                    <EmptyState text="暂无" />
                  ) : (
                    rankingsRes.data.top_removed_days.map((x) => (
                      <div key={x.metric_date} className="list-item">
                        <Link href={`/search${qs({ status: 'cancelled' })}`}>{x.metric_date}</Link> / {x.value}
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
