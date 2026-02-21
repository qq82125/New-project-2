'use client';

import { useMemo, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../../ui/card';
import { Button } from '../../ui/button';
import { Select } from '../../ui/select';
import { Badge } from '../../ui/badge';
import { toast } from '../../ui/use-toast';
import UnifiedTable from '../../table/UnifiedTable';
import type { UnifiedTableRow } from '../../table/columns';
import { buildSearchUrl } from '../../../lib/search-filters';

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
  const [loading, setLoading] = useState(false);
  const [level, setLevel] = useState('HIGH,CRITICAL');

  const filtered = useMemo(() => {
    if (!level) return items;
    const set = new Set(level.split(',').map((x) => x.trim().toUpperCase()));
    return items.filter((x) => set.has(String(x.risk_level || '').toUpperCase()));
  }, [items, level]);

  const rows: UnifiedTableRow[] = useMemo(
    () =>
      filtered.map((it) => {
        const regNo = it.registration_no || '';
        const back = buildSearchUrl({ q: regNo, risk: 'high', sort: 'risk', date_range: '30d' });
        return {
          id: `${it.registration_no}|${it.calculated_at}`,
          product_name: it.product_name || '-',
          company_name: '-',
          registration_no: regNo || '-',
          status: '-',
          expiry_date: '-',
          udi_di: '-',
          badges: [
            { kind: 'risk', value: it.risk_level || 'high' },
            { kind: 'custom', value: `LRI ${(Number(it.lri_norm || 0) * 100).toFixed(1)}%` },
            { kind: 'custom', value: String(it.calculated_at || '-').slice(0, 10) },
          ],
          detail_href: regNo
            ? `/registrations/${encodeURIComponent(regNo)}?back=${encodeURIComponent(back)}`
            : '/search',
        };
      }),
    [filtered],
  );

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
          <Badge variant="muted">共 {filtered.length} 条</Badge>
        </div>
        <UnifiedTable rows={rows} />
      </CardContent>
    </Card>
  );
}

