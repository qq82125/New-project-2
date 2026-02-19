import Link from 'next/link';

import type { EvidenceRef } from '../../lib/api/types';

type EvidencePanelProps = {
  evidenceRefs?: EvidenceRef[];
};

function truncate(text: string, max = 160): string {
  if (text.length <= max) return text;
  return `${text.slice(0, max)}...`;
}

export default function EvidencePanel({ evidenceRefs }: EvidencePanelProps) {
  const items = evidenceRefs || [];

  return (
    <section className="rounded border p-3">
      <h4 className="mb-2 text-sm font-semibold">Evidence</h4>
      {items.length === 0 ? (
        <p className="text-sm text-gray-700">暂无证据引用</p>
      ) : (
        <ul className="space-y-2">
          {items.map((item, idx) => (
            <li key={`${item.source}-${idx}`} className="rounded border p-2 text-sm">
              <p>Source: {item.source}</p>
              {item.source_url ? (
                <p>
                  URL:{' '}
                  <Link href={item.source_url} className="text-blue-700 underline">
                    {item.source_url}
                  </Link>
                </p>
              ) : null}
              {item.page !== undefined ? <p>Page: {String(item.page)}</p> : null}
              {item.excerpt ? <p>Excerpt: {truncate(item.excerpt)}</p> : null}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
