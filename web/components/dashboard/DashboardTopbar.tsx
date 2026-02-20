'use client';

import { FormEvent, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { buildSearchUrl } from '../../lib/search-filters';

export default function DashboardTopbar() {
  const router = useRouter();
  const [q, setQ] = useState('');

  function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    router.push(buildSearchUrl({ q: q.trim() }));
  }

  return (
    <form onSubmit={onSubmit} style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
      <Input
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="全局搜索（回车跳转）"
        aria-label="全局搜索"
        style={{ minWidth: 280, flex: '1 1 360px' }}
      />
      <Button type="submit">搜索</Button>
      <Button type="button" variant="secondary" onClick={() => router.push(buildSearchUrl({ date_range: '7d', sort: 'recency' }))}>
        最近7天
      </Button>
    </form>
  );
}

