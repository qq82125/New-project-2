'use client';

import { useMemo, useState } from 'react';
import { EmptyState } from '../States';
import type { DetailChange } from '../../lib/detail';
import { Button } from '../ui/button';
import type { RegistrationDiffItem } from '../../lib/api/types';
import { resolveFieldGroupTitle, resolveFieldLabel } from './field-dictionaries';

const DEFAULT_LIMIT = 5;

function text(value: unknown): string {
  if (value === null || value === undefined) return '-';
  const v = String(value).trim();
  return v || '-';
}

function groupDiffsByTitle(item: RegistrationDiffItem): Array<{ title: string; rows: RegistrationDiffItem['diffs'] }> {
  const groups = new Map<string, RegistrationDiffItem['diffs']>();
  for (const diff of item.diffs || []) {
    const title = diff.group || resolveFieldGroupTitle(diff.field);
    if (!groups.has(title)) groups.set(title, []);
    groups.get(title)?.push(diff);
  }
  return Array.from(groups.entries()).map(([title, rows]) => ({ title, rows }));
}

type Props = {
  changes: DetailChange[];
  registrationNo?: string;
  initialDiffItems?: RegistrationDiffItem[];
  initialDiffTotal?: number;
};

export default function ChangesTimeline({ changes, registrationNo, initialDiffItems = [], initialDiffTotal = 0 }: Props) {
  const [diffItems, setDiffItems] = useState<RegistrationDiffItem[]>(initialDiffItems);
  const [diffTotal, setDiffTotal] = useState(initialDiffTotal);
  const [loadingMore, setLoadingMore] = useState(false);
  const [showTimeline, setShowTimeline] = useState(false);
  const [timelineExpanded, setTimelineExpanded] = useState(false);
  const visibleTimeline = useMemo(
    () => (timelineExpanded ? changes : changes.slice(0, DEFAULT_LIMIT)),
    [changes, timelineExpanded],
  );

  const hasDiffs = diffItems.length > 0;

  async function onLoadMore() {
    if (!registrationNo || loadingMore || diffItems.length >= diffTotal) return;
    setLoadingMore(true);
    try {
      const resp = await fetch(
        `/api/registrations/${encodeURIComponent(registrationNo)}/diffs?limit=${DEFAULT_LIMIT}&offset=${diffItems.length}`,
        { cache: 'no-store' },
      );
      if (!resp.ok) return;
      const body = await resp.json();
      const data = body?.data || {};
      const nextItems = Array.isArray(data.items) ? (data.items as RegistrationDiffItem[]) : [];
      const total = Number(data.total || diffTotal);
      if (nextItems.length) setDiffItems((prev) => [...prev, ...nextItems]);
      setDiffTotal(total);
    } finally {
      setLoadingMore(false);
    }
  }

  if (!hasDiffs && !changes.length) {
    return <EmptyState text="暂无字段级变更记录" />;
  }

  return (
    <div className="grid" style={{ gap: 10 }}>
      {hasDiffs ? (
        <>
          {diffItems.map((item, idx) => (
            <div key={`${item.snapshot_key || 'snapshot'}:${item.observed_at || ''}:${idx}`} className="card">
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 8 }}>
                <span className="muted">时间：{text(item.observed_at)}</span>
                <span className="muted">版本：{text(item.snapshot_key)}</span>
                <span className="muted">来源：{text(item.source)}</span>
              </div>
              <div className="grid" style={{ gap: 8 }}>
                {groupDiffsByTitle(item).map((group) => (
                  <details key={`${item.snapshot_key}:${group.title}`} open>
                    <summary style={{ cursor: 'pointer', fontWeight: 600 }}>{group.title}</summary>
                    <div className="grid" style={{ gap: 8, marginTop: 8 }}>
                      {group.rows.map((row, rowIdx) => (
                        <div key={`${row.field}:${rowIdx}`} className="columns-2" style={{ gap: 8 }}>
                          <div>{resolveFieldLabel(row.field)}</div>
                          <div>
                            <span className="muted">{text(row.before)}</span>
                            <span style={{ margin: '0 6px' }}>→</span>
                            <span>{text(row.after)}</span>
                            {row.evidence_raw_document_id ? (
                              <span className="muted" style={{ marginLeft: 8 }}>
                                证据#{row.evidence_raw_document_id}
                              </span>
                            ) : null}
                          </div>
                        </div>
                      ))}
                    </div>
                  </details>
                ))}
              </div>
            </div>
          ))}
          {diffItems.length < diffTotal ? (
            <div>
              <Button type="button" variant="secondary" size="sm" disabled={loadingMore} onClick={onLoadMore}>
                {loadingMore ? '加载中...' : `展开更多（已显示 ${diffItems.length}/${diffTotal}）`}
              </Button>
            </div>
          ) : null}
        </>
      ) : (
        <EmptyState text="暂无字段级变更记录" />
      )}

      {changes.length ? (
        <details className="card" open={showTimeline} onToggle={(e) => setShowTimeline((e.target as HTMLDetailsElement).open)}>
          <summary style={{ cursor: 'pointer', fontWeight: 700 }}>Timeline events</summary>
          <div className="grid" style={{ marginTop: 10, gap: 8 }}>
            {visibleTimeline.map((row, idx) => (
              <div key={`${row.field}:${row.observed_at}:${idx}`} className="columns-2" style={{ gap: 8 }}>
                <div>
                  <span className="muted">字段：</span>
                  {row.field || '-'}
                </div>
                <div>
                  <span className="muted">时间：</span>
                  {row.observed_at || '-'}
                </div>
                <div>
                  <span className="muted">旧值：</span>
                  {row.old_value || '-'}
                </div>
                <div>
                  <span className="muted">新值：</span>
                  {row.new_value || '-'}
                </div>
              </div>
            ))}
            {changes.length > DEFAULT_LIMIT ? (
              <div>
                <Button type="button" variant="secondary" size="sm" onClick={() => setTimelineExpanded((v) => !v)}>
                  {timelineExpanded ? '收起 timeline' : `展开 timeline（${changes.length}）`}
                </Button>
              </div>
            ) : null}
          </div>
        </details>
      ) : null}
    </div>
  );
}
