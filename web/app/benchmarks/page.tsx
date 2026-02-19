'use client';

import { useEffect, useMemo, useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../components/ui/card';
import BenchmarkSets from '../../components/benchmarks/BenchmarkSets';
import BenchmarkTable from '../../components/benchmarks/BenchmarkTable';
import { useBenchmarkSets } from '../../lib/benchmarks-store';
import type { UnifiedTableRow } from '../../components/table/columns';

type RegistrationSummary = {
  registration_no: string;
  company?: string | null;
  track?: string | null;
  status?: string | null;
  expiry_date?: string | null;
  variants?: Array<{ di?: string | null }>;
};

type ApiEnvelope<T> = {
  code: number;
  message?: string;
  data: T;
};

async function fetchRegistration(no: string): Promise<RegistrationSummary | null> {
  try {
    const res = await fetch(`/api/registrations/${encodeURIComponent(no)}`, { cache: 'no-store' });
    if (!res.ok) return null;
    const body = (await res.json()) as ApiEnvelope<RegistrationSummary>;
    if (body.code !== 0 || !body.data) return null;
    return body.data;
  } catch {
    return null;
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
      const results = await Promise.all(activeSet.items.map((no) => fetchRegistration(no)));
      if (cancelled) return;
      const back = encodeURIComponent(`/benchmarks?set=${encodeURIComponent(activeSet.id)}`);
      const mapped: UnifiedTableRow[] = results
        .filter((item): item is RegistrationSummary => Boolean(item))
        .map((item) => ({
          id: item.registration_no,
          product_name: item.track || item.registration_no,
          company_name: item.company || '-',
          registration_no: item.registration_no,
          status: item.status || '-',
          expiry_date: item.expiry_date || '-',
          udi_di: item.variants?.[0]?.di || '-',
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
