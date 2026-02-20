import Link from 'next/link';
import { EmptyState, ErrorState } from '../../../components/States';
import CopyButton from '../../../components/common/CopyButton';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../../components/ui/card';
import { apiGet } from '../../../lib/api';

type EvidenceDetail = {
  id: string;
  source_name?: string | null;
  source_url?: string | null;
  observed_at?: string | null;
  title?: string | null;
  excerpts?: Array<{
    text?: string | null;
    field?: string | null;
    page?: number | null;
    registration_no?: string | null;
  }>;
  parse_meta?: {
    parse_status?: string | null;
    run_id?: string | null;
    fetched_at?: string | null;
  } | null;
};

function toText(v: unknown): string {
  if (v === null || v === undefined) return '-';
  const s = String(v).trim();
  return s || '-';
}

export default async function EvidenceDetailPage({
  params,
}: {
  params: Promise<{ raw_document_id: string }>;
}) {
  const { raw_document_id } = await params;
  const res = await apiGet<EvidenceDetail>(`/api/evidence/${encodeURIComponent(raw_document_id)}`);
  if (res.error) {
    return <ErrorState text={`证据加载失败（${res.error}）`} />;
  }

  const data = res.data;
  if (!data) {
    return <EmptyState text="证据不存在" />;
  }

  const appUrl = process.env.NEXT_PUBLIC_APP_URL || '';
  const deepLink = appUrl
    ? `${appUrl.replace(/\/+$/, '')}/evidence/${encodeURIComponent(data.id)}`
    : `/evidence/${encodeURIComponent(data.id)}`;
  const firstExcerpt = data.excerpts?.[0]?.text || '';
  const citation = `[${toText(data.source_name)}] [${toText(data.observed_at)}] [${toText(data.source_url)}]\n引用：${toText(firstExcerpt)}\n证据链接：${deepLink}`;

  return (
    <div className="grid">
      <Card>
        <CardHeader>
          <CardTitle>证据详情</CardTitle>
          <CardDescription>
            <Link href="/search">返回搜索</Link>
          </CardDescription>
        </CardHeader>
        <CardContent className="grid" style={{ gap: 10 }}>
          <div className="columns-2" style={{ gap: 8 }}>
            <div>
              <span className="muted">来源：</span>
              {toText(data.source_name)}
            </div>
            <div>
              <span className="muted">观察时间：</span>
              {toText(data.observed_at)}
            </div>
            <div>
              <span className="muted">源链接：</span>
              {data.source_url ? (
                <a href={data.source_url} target="_blank" rel="noreferrer">
                  {data.source_url}
                </a>
              ) : (
                '-'
              )}
            </div>
            <div>
              <span className="muted">证据ID：</span>
              {data.id}
            </div>
          </div>
          <div style={{ borderTop: '1px solid hsl(var(--border))', margin: '4px 0' }} />
          <div>
            <CopyButton text={citation} label="复制证据引用" size="sm" />
          </div>
          {data.excerpts && data.excerpts.length > 0 ? (
            <div className="grid" style={{ gap: 8 }}>
              {data.excerpts.map((item, idx) => (
                <div key={`${item.field || 'excerpt'}:${idx}`} className="card">
                  <div>
                    <span className="muted">字段：</span>
                    {toText(item.field)}
                  </div>
                  <div>
                    <span className="muted">注册证号：</span>
                    {toText(item.registration_no)}
                  </div>
                  <div>
                    <span className="muted">页码：</span>
                    {toText(item.page)}
                  </div>
                  <div style={{ whiteSpace: 'pre-wrap' }}>{toText(item.text)}</div>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState text="暂无可展示引用片段" />
          )}
        </CardContent>
      </Card>
    </div>
  );
}
