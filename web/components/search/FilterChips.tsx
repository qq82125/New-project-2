'use client';

import { useMemo } from 'react';
import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import { Badge } from '../ui/badge';
import { Button } from '../ui/button';
import { buildSearchUrl, parseSearchUrl, serializeFiltersToChips, type SearchFilters } from '../../lib/search-filters';
import CopyButton from '../common/CopyButton';

export default function FilterChips() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const filters = useMemo(() => parseSearchUrl(new URLSearchParams(searchParams.toString())), [searchParams]);
  const chips = useMemo(() => serializeFiltersToChips(filters), [filters]);
  const fullUrl = useMemo(() => {
    const qs = searchParams.toString();
    if (typeof window === 'undefined') return qs ? `${pathname}?${qs}` : pathname;
    return `${window.location.origin}${pathname}${qs ? `?${qs}` : ''}`;
  }, [pathname, searchParams]);

  function removeChip(key: keyof SearchFilters) {
    const next: Partial<SearchFilters> = { ...filters };
    if (key === 'sort') next.sort = 'recency';
    else if (key === 'view') next.view = 'table';
    else next[key] = '';
    router.push(buildSearchUrl(next));
  }

  function clearAll() {
    router.push('/search');
  }

  if (chips.length === 0) {
    return (
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
        <Badge variant="muted">无筛选</Badge>
        <CopyButton text={fullUrl} />
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
      {chips.map((chip) => (
        <button
          key={chip.key}
          type="button"
          className="ui-btn ui-btn--sm ui-btn--secondary"
          onClick={() => removeChip(chip.key)}
          title="点击移除该筛选"
        >
          {chip.label}: {chip.value} ×
        </button>
      ))}
      <Button type="button" variant="ghost" size="sm" onClick={clearAll}>
        清空全部
      </Button>
      <CopyButton text={fullUrl} />
    </div>
  );
}
