'use client';

import Link from 'next/link';
import { useMemo, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../../ui/card';
import { Button } from '../../ui/button';
import { Select } from '../../ui/select';
import { Badge } from '../../ui/badge';
import { toast } from '../../ui/use-toast';

type Item = {
  registration_no: string;
  product_name?: string | null;
  risk_level: string;
  lri_norm: number;
  calculated_at: string;
};

type Resp = { total: number; items: Item[] };
const LIMIT = 20;

export default function HighRiskQueueClient({ initialItems }: { initialItems: Item[] }) {
  const [items, setItems] = useState<Item[]>(initialItems || []);
  const [selected, setSelected] = useState<Record<string, boolean>>({});
  const [loading, setLoading] = useState(false);
  const [level, setLevel] = useState('HIGH,CRITICAL');

  const filtered = useMemo(() => {
    if (!level) return items;
    const set = new Set(level.split(',').map((x) => x.trim().toUpperCase()));
    return items.filter((x) => set.has(String(x.risk_level || '').toUpperCase()));
  }, [items, level]);

  async function loadMore() {
    setLoading(true);
    try {
      const res = await fetch(`/api/admin/lri?limit=${LIMIT}&offset=${items.length}`, { credentials: 'include', cache: 'no-store' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const body = (await res.json()) as Resp;
      const next = body?.items || [];
      setItems((prev) => [...prev, ...next.filter((x) => !prev.some((p) => p.registration_no === x.registration_no && p.calculated_at === x.calculated_at))]);
    } catch (e) {
      toast({ variant: 'destructive', title: '加载失败', description: String((e as Error)?.message || e) });
    } finally {
      setLoading(false);
    }
  }

  function batchIgnore() {
    const keys = Object.keys(selected).filter((k) => selected[k]);
    if (!keys.length) {
      toast({ variant: 'destructive', title: '未选择', description: '请先选择要忽略的条目' });
      return;
    }
    setItems((prev) => prev.filter((x) => !keys.includes(`${x.registration_no}|${x.calculated_at}`)));
    setSelected({});
    toast({ title: '批量忽略', description: `已忽略 ${keys.length} 条` });
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>LRI 高风险</CardTitle>
      </CardHeader>
      <CardContent className="grid">
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
          <Select value={level} onChange={(e) => setLevel(e.target.value)}>
            <option value="HIGH,CRITICAL">高风险</option>
            <option value="MID">中风险</option>
            <option value="LOW">低风险</option>
            <option value="LOW,MID,HIGH,CRITICAL">全部</option>
          </Select>
          <Button type="button" variant="secondary" onClick={() => void loadMore()} disabled={loading}>
            {loading ? '加载中…' : '加载更多'}
          </Button>
          <Button type="button" onClick={batchIgnore}>批量忽略</Button>
          <Badge variant="muted">共 {filtered.length} 条</Badge>
        </div>

        <div style={{ overflowX: 'auto' }}>
          <table className="table">
            <thead>
              <tr>
                <th style={{ width: 40 }}></th>
                <th>注册证号</th>
                <th>产品</th>
                <th>风险</th>
                <th>分数</th>
                <th>时间</th>
                <th>下钻</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((it) => {
                const key = `${it.registration_no}|${it.calculated_at}`;
                return (
                  <tr key={key}>
                    <td>
                      <input
                        type="checkbox"
                        checked={Boolean(selected[key])}
                        onChange={(e) => setSelected((prev) => ({ ...prev, [key]: e.target.checked }))}
                      />
                    </td>
                    <td className="mono">{it.registration_no || '-'}</td>
                    <td>{it.product_name || '-'}</td>
                    <td>{it.risk_level || '-'}</td>
                    <td>{(Number(it.lri_norm || 0) * 100).toFixed(1)}%</td>
                    <td>{String(it.calculated_at || '-').slice(0, 19).replace('T', ' ')}</td>
                    <td>
                      <Link href={`/registrations/${encodeURIComponent(it.registration_no || '')}`}>查看</Link>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
}
