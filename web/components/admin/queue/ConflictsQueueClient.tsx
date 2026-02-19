'use client';

import Link from 'next/link';
import { useMemo, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../../ui/card';
import { Button } from '../../ui/button';
import { Input } from '../../ui/input';
import { Badge } from '../../ui/badge';
import { toast } from '../../ui/use-toast';

type Item = {
  id: string;
  registration_no: string;
  field_name: string;
  status: string;
  created_at?: string | null;
};

type Resp = { code: number; message: string; data: { items: Item[]; count: number; status: string } };
const LIMIT = 20;

export default function ConflictsQueueClient({ initialItems }: { initialItems: Item[] }) {
  const [items, setItems] = useState<Item[]>(initialItems || []);
  const [query, setQuery] = useState('');
  const [selected, setSelected] = useState<Record<string, boolean>>({});
  const [loading, setLoading] = useState(false);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return items;
    return items.filter((x) =>
      String(x.field_name || '').toLowerCase().includes(q) ||
      String(x.registration_no || '').toLowerCase().includes(q)
    );
  }, [items, query]);

  async function loadMore() {
    setLoading(true);
    try {
      const res = await fetch(`/api/admin/conflicts?status=open&limit=${LIMIT}&offset=${items.length}`, {
        credentials: 'include',
        cache: 'no-store',
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const body = (await res.json()) as Resp;
      const next = body?.data?.items || [];
      setItems((prev) => [...prev, ...next.filter((x) => !prev.some((p) => p.id === x.id))]);
    } catch (e) {
      toast({ variant: 'destructive', title: '加载失败', description: String((e as Error)?.message || e) });
    } finally {
      setLoading(false);
    }
  }

  function batchMarkProcessed() {
    const ids = Object.keys(selected).filter((id) => selected[id]);
    if (!ids.length) {
      toast({ variant: 'destructive', title: '未选择', description: '请先选择要处理的条目' });
      return;
    }
    setItems((prev) => prev.filter((x) => !ids.includes(x.id)));
    setSelected({});
    toast({ title: '批量标记已处理', description: `已处理 ${ids.length} 条` });
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>冲突待裁决</CardTitle>
      </CardHeader>
      <CardContent className="grid">
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }} data-testid="admin_queue__filters__panel">
          <Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="按字段名 / 注册证号筛选" />
          <Button type="button" variant="secondary" onClick={() => void loadMore()} disabled={loading} data-testid="admin_queue__list__load_more">
            {loading ? '加载中…' : '加载更多'}
          </Button>
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }} data-testid="admin_queue__bulk__panel">
          <Button type="button" onClick={batchMarkProcessed}>批量标记已处理</Button>
          <Badge variant="muted">共 {filtered.length} 条</Badge>
        </div>

        <div style={{ overflowX: 'auto' }} data-testid="admin_queue__list__panel">
          <table className="table">
            <thead>
              <tr>
                <th style={{ width: 40 }}></th>
                <th>注册证号</th>
                <th>字段</th>
                <th>时间</th>
                <th>状态</th>
                <th>下钻</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((it) => (
                <tr key={it.id}>
                  <td>
                    <input
                      type="checkbox"
                      checked={Boolean(selected[it.id])}
                      onChange={(e) => setSelected((prev) => ({ ...prev, [it.id]: e.target.checked }))}
                    />
                  </td>
                  <td className="mono">{it.registration_no || '-'}</td>
                  <td>{it.field_name || '-'}</td>
                  <td>{String(it.created_at || '-').slice(0, 19).replace('T', ' ')}</td>
                  <td>{it.status || '-'}</td>
                  <td>
                    <Link href={`/registrations/${encodeURIComponent(it.registration_no || '')}`}>查看</Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}
