'use client';

import { useMemo, useState } from 'react';
import { Badge } from '../ui/badge';

export type PackingEdge = {
  package_di?: string | null;
  package_level?: string | null;
  contains_qty?: number | null;
  child_di?: string | null;
};

type Edge = {
  child: string;
  qty: number | null;
};

function asStr(v: any): string | null {
  const s = String(v ?? '').trim();
  return s ? s : null;
}

function asNum(v: any): number | null {
  if (v === null || v === undefined) return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

function buildGraph(packings: PackingEdge[]) {
  const childrenByParent = new Map<string, Edge[]>();
  const levelByDi = new Map<string, string | null>();
  const childSet = new Set<string>();

  for (const p of packings || []) {
    const parent = asStr(p.package_di);
    if (!parent) continue;
    const child = asStr(p.child_di);
    const qty = asNum(p.contains_qty);

    if (!levelByDi.has(parent)) levelByDi.set(parent, asStr(p.package_level));
    if (child) childSet.add(child);

    const arr = childrenByParent.get(parent) || [];
    if (child) arr.push({ child, qty });
    childrenByParent.set(parent, arr);
  }

  const parents = Array.from(childrenByParent.keys());
  const roots = parents.filter((p) => !childSet.has(p));
  return { childrenByParent, levelByDi, roots: roots.length ? roots : parents };
}

function Node({
  di,
  childrenByParent,
  levelByDi,
  depth,
  visited,
}: {
  di: string;
  childrenByParent: Map<string, Edge[]>;
  levelByDi: Map<string, string | null>;
  depth: number;
  visited: Set<string>;
}) {
  const children = childrenByParent.get(di) || [];
  const level = levelByDi.get(di);

  if (visited.has(di)) {
    return (
      <div style={{ paddingLeft: depth * 14 }}>
        <span className="muted">↺ 循环引用: {di}</span>
      </div>
    );
  }

  const nextVisited = new Set(visited);
  nextVisited.add(di);

  if (children.length === 0) {
    return (
      <div style={{ paddingLeft: depth * 14, display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
        <Badge variant="muted">{level ? `${level}` : 'DI'}</Badge>
        <span>{di}</span>
      </div>
    );
  }

  return (
    <details open={depth <= 0} style={{ paddingLeft: depth * 14 }}>
      <summary style={{ cursor: 'pointer', display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
        <Badge variant="muted">{level ? `${level}` : '包装'}</Badge>
        <span>{di}</span>
        <span className="muted">· 子项 {children.length}</span>
      </summary>
      <div style={{ marginTop: 8 }} className="grid">
        {children.slice(0, 200).map((e, idx) => {
          const hasSub = childrenByParent.has(e.child);
          return (
            <div key={`${di}:${idx}`} className="grid" style={{ gap: 6 }}>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap', paddingLeft: 14 }}>
                <span className="muted">→</span>
                <span>{e.child}</span>
                {e.qty != null ? <Badge variant="muted">包含数量: {e.qty}</Badge> : <Badge variant="muted">包含数量: -</Badge>}
                {!hasSub ? <span className="muted">（叶子 DI）</span> : null}
              </div>
              {hasSub ? (
                <Node di={e.child} childrenByParent={childrenByParent} levelByDi={levelByDi} depth={depth + 1} visited={nextVisited} />
              ) : null}
            </div>
          );
        })}
      </div>
    </details>
  );
}

export default function PackagingTree({ packings }: { packings: PackingEdge[] }) {
  const { childrenByParent, levelByDi, roots } = useMemo(() => buildGraph(packings || []), [packings]);
  const [showAllRoots, setShowAllRoots] = useState(false);

  if (!packings || packings.length === 0) return <div className="muted">无包装层级信息</div>;
  if (roots.length === 0) return <div className="muted">无可用的包装层级根节点</div>;

  const rootsToShow = showAllRoots ? roots : roots.slice(0, 3);

  return (
    <div className="grid">
      {roots.length > 3 ? (
        <button
          type="button"
          onClick={() => setShowAllRoots((v) => !v)}
          style={{ background: 'transparent', border: 'none', padding: 0, cursor: 'pointer', textDecoration: 'underline' }}
        >
          {showAllRoots ? '收起根节点' : `展开全部根节点（${roots.length}）`}
        </button>
      ) : null}
      {rootsToShow.map((r) => (
        <Node key={r} di={r} childrenByParent={childrenByParent} levelByDi={levelByDi} depth={0} visited={new Set()} />
      ))}
    </div>
  );
}
