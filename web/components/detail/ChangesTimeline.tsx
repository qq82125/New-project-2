'use client';

import { useMemo, useState } from 'react';
import { EmptyState } from '../States';
import type { DetailChange } from '../../lib/detail';
import { Button } from '../ui/button';

const DEFAULT_LIMIT = 5;

export default function ChangesTimeline({ changes }: { changes: DetailChange[] }) {
  const [expanded, setExpanded] = useState(false);
  const visible = useMemo(() => (expanded ? changes : changes.slice(0, DEFAULT_LIMIT)), [changes, expanded]);

  if (!changes.length) {
    return <EmptyState text="暂无字段变更记录" />;
  }

  return (
    <div className="grid">
      {visible.map((row, idx) => (
        <div key={`${row.field}:${row.observed_at}:${idx}`} className="card">
          <div className="columns-2" style={{ gap: 8 }}>
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
        </div>
      ))}
      {changes.length > DEFAULT_LIMIT ? (
        <div>
          <Button type="button" variant="secondary" size="sm" onClick={() => setExpanded((v) => !v)}>
            {expanded ? '收起' : `展开全部（${changes.length}）`}
          </Button>
        </div>
      ) : null}
    </div>
  );
}
