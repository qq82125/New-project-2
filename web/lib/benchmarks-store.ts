'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';

export type BenchmarkSet = {
  id: string;
  name: string;
  items: string[];
};

const STORAGE_KEY = 'benchmark_sets';
const UPDATE_EVENT = 'benchmark-updated';

const DEFAULT_SETS: BenchmarkSet[] = [
  { id: 'my-benchmark', name: 'My Benchmark', items: [] },
  { id: 'high-risk-pool', name: 'High Risk Pool', items: [] },
];

function uniqueItems(items: string[]): string[] {
  return Array.from(new Set(items.map((v) => String(v || '').trim()).filter(Boolean)));
}

function normalizeSet(input: BenchmarkSet): BenchmarkSet {
  return {
    id: String(input.id || '').trim(),
    name: String(input.name || '').trim() || 'Unnamed',
    items: uniqueItems(input.items || []),
  };
}

function mergeWithDefaults(inputSets: BenchmarkSet[]): BenchmarkSet[] {
  const map = new Map<string, BenchmarkSet>();
  for (const set of DEFAULT_SETS) {
    map.set(set.id, { ...set, items: uniqueItems(set.items) });
  }
  for (const raw of inputSets) {
    const set = normalizeSet(raw);
    if (!set.id) continue;
    const prev = map.get(set.id);
    map.set(set.id, {
      id: set.id,
      name: set.name || prev?.name || set.id,
      items: uniqueItems([...(prev?.items || []), ...set.items]),
    });
  }
  return Array.from(map.values());
}

export function readBenchmarkSets(): BenchmarkSet[] {
  if (typeof window === 'undefined') return DEFAULT_SETS;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULT_SETS;
    const parsed = JSON.parse(raw) as BenchmarkSet[];
    if (!Array.isArray(parsed)) return DEFAULT_SETS;
    return mergeWithDefaults(parsed);
  } catch {
    return DEFAULT_SETS;
  }
}

function emitUpdate() {
  if (typeof window === 'undefined') return;
  window.dispatchEvent(new Event(UPDATE_EVENT));
}

export function writeBenchmarkSets(sets: BenchmarkSet[]): void {
  if (typeof window === 'undefined') return;
  const normalized = mergeWithDefaults(sets);
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(normalized));
  emitUpdate();
}

export function isInBenchmarkSet(sets: BenchmarkSet[], setId: string, registrationNo: string): boolean {
  const target = sets.find((set) => set.id === setId);
  if (!target) return false;
  return target.items.includes(String(registrationNo || '').trim());
}

export function toggleBenchmarkItem(sets: BenchmarkSet[], setId: string, registrationNo: string): BenchmarkSet[] {
  const no = String(registrationNo || '').trim();
  if (!no) return sets;
  return sets.map((set) => {
    if (set.id !== setId) return set;
    const exists = set.items.includes(no);
    return {
      ...set,
      items: exists ? set.items.filter((x) => x !== no) : uniqueItems([...set.items, no]),
    };
  });
}

export function useBenchmarkSets() {
  const [sets, setSets] = useState<BenchmarkSet[]>(DEFAULT_SETS);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const sync = () => setSets(readBenchmarkSets());
    sync();
    setReady(true);
    window.addEventListener('storage', sync);
    window.addEventListener(UPDATE_EVENT, sync);
    return () => {
      window.removeEventListener('storage', sync);
      window.removeEventListener(UPDATE_EVENT, sync);
    };
  }, []);

  const save = useCallback((next: BenchmarkSet[]) => {
    writeBenchmarkSets(next);
    setSets(readBenchmarkSets());
  }, []);

  const toggle = useCallback((setId: string, registrationNo: string) => {
    setSets((prev) => {
      const next = toggleBenchmarkItem(prev, setId, registrationNo);
      writeBenchmarkSets(next);
      return readBenchmarkSets();
    });
  }, []);

  const api = useMemo(
    () => ({
      ready,
      sets,
      save,
      toggle,
    }),
    [ready, sets, save, toggle],
  );

  return api;
}
