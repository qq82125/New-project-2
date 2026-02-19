import { EmptyState } from '../States';
import type { DetailEvidence } from '../../lib/detail';

export default function EvidenceList({ evidences }: { evidences: DetailEvidence[] }) {
  if (!evidences.length) {
    return <EmptyState text="暂无可追溯证据（来源与抓取时间缺失）" />;
  }

  return (
    <div className="grid">
      {evidences.map((item, idx) => (
        <div key={`${item.source}:${item.observed_at}:${idx}`} className="card">
          <div>
            <span className="muted">来源：</span>
            {item.source || '-'}
          </div>
          <div>
            <span className="muted">观察时间：</span>
            {item.observed_at || '-'}
          </div>
          <div>
            <span className="muted">引用：</span>
            {item.excerpt ? (
              item.excerpt.length > 120 ? (
                <details>
                  <summary>show more</summary>
                  <div style={{ marginTop: 6, whiteSpace: 'pre-wrap' }}>{item.excerpt}</div>
                </details>
              ) : (
                <span>{item.excerpt}</span>
              )
            ) : (
              <span>-</span>
            )}
          </div>
          {item.raw_document_id ? (
            <div>
              <span className="muted">raw_document：</span>
              {item.raw_document_url ? (
                <a href={item.raw_document_url} target="_blank" rel="noreferrer">
                  {item.raw_document_id}
                </a>
              ) : (
                <span>{item.raw_document_id}</span>
              )}
            </div>
          ) : null}
        </div>
      ))}
    </div>
  );
}
