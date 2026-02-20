'use client';

import { useEffect, useMemo, useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card';
import BenchmarkSets from '../../components/benchmarks/BenchmarkSets';
import BenchmarkTable from '../../components/benchmarks/BenchmarkTable';
import { useBenchmarkSets } from '../../lib/benchmarks-store';
import type { UnifiedTableRow } from '../../components/table/columns';

type BenchmarkBatchItem = {
  registration_no: string;
  name?: string | null;
  company?: string | null;
  track?: string | null;
  status?: string | null;
  expiry?: string | null;
  di_count?: number | null;
  change_count_30d?: number | null;
  params_coverage?: number | null;
  risk_level?: string | null;
};

type ApiEnvelope<T> = {
  code: number;
  message?: string;
  data: T;
};

type BatchData = {
  items: BenchmarkBatchItem[];
  total: number;
};

async function fetchRegistrationBatch(nos: string[]): Promise<BenchmarkBatchItem[]> {
  try {
    const res = await fetch('/api/registrations/batch', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ nos }),
      cache: 'no-store',
    });
    if (!res.ok) return [];
    const body = (await res.json()) as ApiEnvelope<BatchData>;
    if (body.code !== 0 || !body.data || !Array.isArray(body.data.items)) return [];
    return body.data.items;
  } catch {
    return [];
  }
}

export default function BenchmarksPage() {
  const { ready, sets } = useBenchmarkSets();
  const [activeSetId, setActiveSetId] = useState('my-benchmark');
  const [loading, setLoading] = useState(false);
  const [rows, setRows] = useState<UnifiedTableRow[]>([]);

  const activeSet = useMemo(() => sets.find((set) => set.id === activeSetId) || sets[0] || null, [sets, activeSetId]);

  useEffect(() => {
    if (!ready || !activeSet) return;
    let cancelled = false;
    async function load() {
      setLoading(true);
      const results = await fetchRegistrationBatch(activeSet.items);
      if (cancelled) return;
      const back = encodeURIComponent(`/benchmarks?set=${encodeURIComponent(activeSet.id)}`);
      const mapped: UnifiedTableRow[] = results
        .map((item) => ({
          id: item.registration_no,
          product_name: item.name || item.track || item.registration_no,
          company_name: item.company || '-',
          registration_no: item.registration_no,
          status: item.status || '-',
          expiry_date: item.expiry || '-',
          udi_di: '-',
          change_count_30d: Number(item.change_count_30d || 0),
          di_count: Number(item.di_count || 0),
          params_coverage: Number(item.params_coverage || 0),
          risk_level: item.risk_level || 'low',
          badges: [
            ...(item.track ? [{ kind: 'track' as const, value: item.track }] : []),
          ],
          detail_href: `/registrations/${encodeURIComponent(item.registration_no)}?back=${back}`,
          action: {
            type: 'benchmark',
            registration_no: item.registration_no,
            set_id: activeSet.id,
          },
        }));
      setRows(mapped);
      setLoading(false);
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [ready, activeSet]);

  useEffect(() => {
    if (!ready) return;
    const sp = new URLSearchParams(window.location.search);
    const set = String(sp.get('set') || '').trim();
    if (set && sets.some((x) => x.id === set)) {
      setActiveSetId(set);
    }
  }, [ready, sets]);

  return (
    <div className="columns-2" style={{ alignItems: 'start' }}>
      <Card>
        <CardHeader>
          <CardTitle>Benchmark Sets</CardTitle>
          <CardDescription>本地对标集合（MVP）</CardDescription>
        </CardHeader>
        <CardContent>
          <BenchmarkSets
            sets={sets}
            activeSetId={activeSet?.id || activeSetId}
            onSelect={(id) => {
              setActiveSetId(id);
              const sp = new URLSearchParams(window.location.search);
              sp.set('set', id);
              window.history.replaceState(null, '', `/benchmarks?${sp.toString()}`);
            }}
          />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{activeSet?.name || 'Benchmarks'}</CardTitle>
          <CardDescription>点击行进入 Detail（保留 back）</CardDescription>
        </CardHeader>
        <CardContent>
          <BenchmarkTable rows={rows} loading={loading} />
        </CardContent>
      </Card>
    </div>
  );
}
