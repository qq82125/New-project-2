'use client';

import Link from 'next/link';
import { EmptyState } from '../States';
import type { DetailEvidence } from '../../lib/detail';
import CopyButton from '../common/CopyButton';

function toText(v: unknown): string {
  if (v === null || v === undefined) return '-';
  const s = String(v).trim();
  return s || '-';
}

function buildCitation(item: DetailEvidence): string {
  const origin =
    (typeof window !== 'undefined' && window.location?.origin) || process.env.NEXT_PUBLIC_APP_URL || '';
  const deepLink = `${String(origin).replace(/\/+$/, '')}/evidence/${encodeURIComponent(item.raw_document_id)}`;
  return `[${toText(item.source)}] [${toText(item.observed_at)}] [${toText(item.raw_document_url)}]\n引用：${toText(item.excerpt)}\n证据链接：${deepLink}`;
}

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
            <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
              <span className="muted">raw_document：</span>
              {item.raw_document_url ? (
                <a href={item.raw_document_url} target="_blank" rel="noreferrer">
                  {item.raw_document_id}
                </a>
              ) : (
                <span>{item.raw_document_id}</span>
              )}
              <Link href={`/evidence/${encodeURIComponent(item.raw_document_id)}`}>查看证据</Link>
              <CopyButton text={buildCitation(item)} label="复制引用" size="sm" />
            </div>
          ) : null}
        </div>
      ))}
    </div>
  );
}
