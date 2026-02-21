'use client';

import { FormEvent, useEffect, useMemo, useState } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Select } from '../ui/select';
import { toast } from '../ui/use-toast';
import {
  buildSearchUrl,
  SEARCH_FILTER_DEFAULTS,
  type SearchChangeType,
  type SearchDateRange,
  type SearchFilters,
  type SearchRisk,
  type SearchSort,
  type SearchView,
} from '../../lib/search-filters';

type SavedView = {
  id: string;
  name: string;
  form: SearchFilters;
};

const STORAGE_KEY = 'search_saved_views_v2';

function normalize(input: Partial<SearchFilters>): SearchFilters {
  const next: SearchFilters = {
    ...SEARCH_FILTER_DEFAULTS,
    ...input,
  };
  return {
    q: String(next.q || ''),
    track: String(next.track || ''),
    company: String(next.company || ''),
    country_or_region: String(next.country_or_region || ''),
    status: String(next.status || ''),
    change_type: String(next.change_type || '') as SearchChangeType | '',
    date_range: String(next.date_range || '') as SearchDateRange | '',
    risk: String(next.risk || '') as SearchRisk | '',
    sort: String(next.sort || 'recency') as SearchSort,
    view: String(next.view || 'table') as SearchView,
  };
}

function readSavedViews(): SavedView[] {
  if (typeof window === 'undefined') return [];
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as SavedView[];
    if (!Array.isArray(parsed)) return [];
    return parsed
      .filter((x) => x && typeof x.id === 'string' && typeof x.name === 'string' && x.form)
      .map((x) => ({ id: x.id, name: x.name, form: normalize(x.form) }));
  } catch {
    return [];
  }
}

function writeSavedViews(views: SavedView[]) {
  if (typeof window === 'undefined') return;
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(views));
}

export default function SearchFiltersPanel({ initial }: { initial: SearchFilters }) {
  const router = useRouter();
  const pathname = usePathname();
  const [form, setForm] = useState<SearchFilters>(normalize(initial));
  const [savedViews, setSavedViews] = useState<SavedView[]>([]);
  const [selectedViewId, setSelectedViewId] = useState('');

  const [openBasic, setOpenBasic] = useState(true);
  const [openAdvanced, setOpenAdvanced] = useState(true);

  useEffect(() => {
    setForm(normalize(initial));
  }, [initial]);

  useEffect(() => {
    setSavedViews(readSavedViews());
  }, []);

  function updateUrl(next: SearchFilters) {
    const href = buildSearchUrl(next);
    if (pathname !== '/search') {
      const query = href.split('?')[1];
      router.push(query ? `${pathname}?${query}` : pathname);
      return;
    }
    router.push(href);
  }

  function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    updateUrl(form);
  }

  function saveView() {
    const name = window.prompt('请输入视图名称');
    if (!name || !name.trim()) return;
    const trimmed = name.trim();
    const next: SavedView = { id: `${Date.now()}`, name: trimmed, form: normalize(form) };
    const merged = [next, ...savedViews.filter((x) => x.name !== trimmed)].slice(0, 20);
    setSavedViews(merged);
    setSelectedViewId(next.id);
    writeSavedViews(merged);
    toast({ title: '保存成功', description: `已保存视图：${trimmed}` });
  }

  function applySavedView(id: string) {
    setSelectedViewId(id);
    if (!id) return;
    const view = savedViews.find((x) => x.id === id);
    if (!view) return;
    setForm(view.form);
    updateUrl(view.form);
  }

  function deleteSavedView() {
    if (!selectedViewId) {
      toast({ variant: 'destructive', title: '删除失败', description: '请先选择一个视图' });
      return;
    }
    const view = savedViews.find((x) => x.id === selectedViewId);
    const next = savedViews.filter((x) => x.id !== selectedViewId);
    setSavedViews(next);
    setSelectedViewId('');
    writeSavedViews(next);
    toast({ title: '已删除', description: view ? `已删除视图：${view.name}` : '视图已删除' });
  }

  const unsupportedHint = useMemo(() => '部分筛选仅用于可分享链接，后端暂未执行。', []);

  return (
    <div className="grid" style={{ gap: 12 }}>
      <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
        <Select value={selectedViewId} onChange={(e) => applySavedView(e.target.value)} style={{ minWidth: 220 }}>
          <option value="">选择已保存视图</option>
          {savedViews.map((view) => (
            <option key={view.id} value={view.id}>
              {view.name}
            </option>
          ))}
        </Select>
        <Button type="button" onClick={saveView}>保存视图</Button>
        <Button type="button" variant="secondary" onClick={deleteSavedView}>删除视图</Button>
      </div>

      <form className="grid" style={{ gap: 10 }} onSubmit={onSubmit}>
        <div className="card" style={{ display: 'grid', gap: 10 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 10 }}>
            <strong>基础筛选</strong>
            <Button type="button" size="sm" variant="ghost" onClick={() => setOpenBasic((v) => !v)}>
              {openBasic ? '折叠' : '展开'}
            </Button>
          </div>
          {openBasic ? (
            <div className="controls">
              <Input value={form.q} onChange={(e) => setForm((s) => ({ ...s, q: e.target.value }))} placeholder="关键词" />
              <Input value={form.track} onChange={(e) => setForm((s) => ({ ...s, track: e.target.value }))} placeholder="赛道" />
              <Input value={form.company} onChange={(e) => setForm((s) => ({ ...s, company: e.target.value }))} placeholder="企业" />
              <Input value={form.country_or_region} onChange={(e) => setForm((s) => ({ ...s, country_or_region: e.target.value }))} placeholder="国家/地区" />
              <Input value={form.status} onChange={(e) => setForm((s) => ({ ...s, status: e.target.value }))} placeholder="状态" />
            </div>
          ) : null}
        </div>

        <div className="card" style={{ display: 'grid', gap: 10 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 10 }}>
            <strong>高级筛选</strong>
            <Button type="button" size="sm" variant="ghost" onClick={() => setOpenAdvanced((v) => !v)}>
              {openAdvanced ? '折叠' : '展开'}
            </Button>
          </div>
          {openAdvanced ? (
            <div className="controls">
              <Select value={form.change_type} onChange={(e) => setForm((s) => ({ ...s, change_type: e.target.value as SearchChangeType | '' }))}>
                <option value="">变更类型（全部）</option>
                <option value="new">new</option>
                <option value="update">update</option>
                <option value="cancel">cancel</option>
              </Select>
              <Select value={form.date_range} onChange={(e) => setForm((s) => ({ ...s, date_range: e.target.value as SearchDateRange | '' }))}>
                <option value="">时间窗（全部）</option>
                <option value="7d">7d</option>
                <option value="30d">30d</option>
                <option value="90d">90d</option>
                <option value="12m">12m</option>
              </Select>
              <Select value={form.risk} onChange={(e) => setForm((s) => ({ ...s, risk: e.target.value as SearchRisk | '' }))}>
                <option value="">风险（全部）</option>
                <option value="high">high</option>
                <option value="medium">medium</option>
                <option value="low">low</option>
              </Select>
              <Select value={form.sort} onChange={(e) => setForm((s) => ({ ...s, sort: e.target.value as SearchSort }))}>
                <option value="recency">recency</option>
                <option value="risk">risk</option>
                <option value="lri">lri</option>
                <option value="competition">competition</option>
              </Select>
              <Select value={form.view} onChange={(e) => setForm((s) => ({ ...s, view: e.target.value as SearchView }))}>
                <option value="table">table</option>
                <option value="compact">compact</option>
              </Select>
            </div>
          ) : null}
          <div className="muted" style={{ fontSize: 12 }}>{unsupportedHint}</div>
        </div>

        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
          <Button type="submit">查询</Button>
        </div>
      </form>
    </div>
  );
}
