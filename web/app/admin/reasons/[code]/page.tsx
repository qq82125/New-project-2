import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../../../components/ui/card';
import { adminFetchJson } from '../../../../lib/admin';
import ReasonTicketCopyButton from './ReasonTicketCopyButton';

type PendingStats = {
  by_reason_code: Array<{ reason_code: string; pending: number }>;
};

type PendingDocItem = {
  id: string;
  raw_document_id: string;
  source_run_id?: number | null;
  reason_code: string;
  created_at?: string | null;
};

type PendingDocResp = {
  items: PendingDocItem[];
  count: number;
  total?: number;
};

export const dynamic = 'force-dynamic';

export default async function AdminReasonDetailPage({ params }: { params: Promise<{ code: string }> }) {
  const { code } = await params;
  const reasonCode = decodeURIComponent(code || 'UNKNOWN');
  const stats = await adminFetchJson<PendingStats>('/api/admin/pending-documents/stats').catch(() => ({ by_reason_code: [] }));
  const total = Number((stats.by_reason_code || []).find((x) => x.reason_code === reasonCode)?.pending || 0);

  const data = await adminFetchJson<PendingDocResp>('/api/admin/pending-documents?status=pending&limit=200&offset=0&order_by=created_at%20desc').catch(
    () => ({ items: [] as PendingDocItem[], count: 0 })
  );
  const samples = (data.items || []).filter((x) => (x.reason_code || 'UNKNOWN') === reasonCode).slice(0, 10);
  const sampleIds = samples.map((x) => x.raw_document_id || x.id).slice(0, 3);
  while (sampleIds.length < 3) {
    sampleIds.push(`NA-${sampleIds.length + 1}`);
  }

  const ticketText = [
    `reason_code: ${reasonCode}`,
    `sample_ids: ${sampleIds.join(', ')}`,
    '复现路径: 进入 /admin/reasons/' + encodeURIComponent(reasonCode) + '，查看样本并在 /admin/queue/pending-docs 重试处理',
    '建议修复点: 1) 补齐解析规则映射 2) 校验源字段必填约束 3) 对该 reason_code 增加告警与回归样例',
  ].join('\n');

  return (
    <div className="grid">
      <Card>
        <CardHeader>
          <CardTitle data-testid="admin_reason__header__title">原因码详情</CardTitle>
          <CardDescription>reason_code: {reasonCode}</CardDescription>
        </CardHeader>
        <CardContent className="grid">
          <div>统计数：{total}</div>
          <ReasonTicketCopyButton text={ticketText} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>样本（10 条）</CardTitle>
          <CardDescription>样本ID / 来源 / 时间 / 错误摘要</CardDescription>
        </CardHeader>
        <CardContent data-testid="admin_reason__sample__list">
          {samples.length === 0 ? (
            <div className="muted">暂无数据</div>
          ) : (
            <table className="table">
              <thead>
                <tr>
                  <th>样本ID</th>
                  <th>来源</th>
                  <th>时间</th>
                  <th>错误摘要</th>
                </tr>
              </thead>
              <tbody>
                {samples.map((x) => (
                  <tr key={x.id}>
                    <td className="mono">{x.raw_document_id || x.id}</td>
                    <td>{x.source_run_id ?? '-'}</td>
                    <td>{String(x.created_at || '-').slice(0, 19).replace('T', ' ')}</td>
                    <td>{x.reason_code || '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
