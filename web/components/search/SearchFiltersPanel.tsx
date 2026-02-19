'use client';

import { FormEvent, useEffect, useMemo, useState } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Select } from '../ui/select';
import { Badge } from '../ui/badge';
import { toast } from '../ui/use-toast';

type SearchFormState = {
  q: string;
  company: string;
  reg_no: string;
  status: string;
  sort_by: string;
  sort_order: string;
  include_pending: boolean;
};

type SavedView = {
  id: string;
  name: string;
  form: SearchFormState;
};

const STORAGE_KEY = 'search_saved_views_v1';

function normalize(input: Partial<SearchFormState>): SearchFormState {
  return {
    q: String(input.q || ''),
    company: String(input.company || ''),
    reg_no: String(input.reg_no || ''),
    status: String(input.status || ''),
    sort_by: String(input.sort_by || 'updated_at'),
    sort_order: String(input.sort_order || 'desc'),
    include_pending: Boolean(input.include_pending),
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

export default function SearchFiltersPanel({ initial }: { initial: SearchFormState }) {
  const router = useRouter();
  const pathname = usePathname();
  const [form, setForm] = useState<SearchFormState>(normalize(initial));
  const [savedViews, setSavedViews] = useState<SavedView[]>([]);
  const [selectedViewId, setSelectedViewId] = useState('');

  const [openBasic, setOpenBasic] = useState(true);
  const [openScope, setOpenScope] = useState(true);
  const [openRisk, setOpenRisk] = useState(false);

  useEffect(() => {
    setForm(normalize(initial));
  }, [initial.q, initial.company, initial.reg_no, initial.status, initial.sort_by, initial.sort_order, initial.include_pending]);

  useEffect(() => {
    setSavedViews(readSavedViews());
  }, []);

  function updateUrl(next: SearchFormState) {
    const qs = new URLSearchParams();
    if (next.q) qs.set('q', next.q);
    if (next.company) qs.set('company', next.company);
    if (next.reg_no) qs.set('reg_no', next.reg_no);
    if (next.status) qs.set('status', next.status);
    if (next.sort_by && next.sort_by !== 'updated_at') qs.set('sort_by', next.sort_by);
    if (next.sort_order && next.sort_order !== 'desc') qs.set('sort_order', next.sort_order);
    if (next.include_pending) qs.set('include_pending', '1');
    router.push(`${pathname}?${qs.toString()}`);
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

  const riskHint = useMemo(() => '后端未接入', []);

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
              <Input value={form.q} onChange={(e) => setForm((s) => ({ ...s, q: e.target.value }))} placeholder="关键词（产品名/注册证号/UDI-DI）" />
              <Input value={form.company} onChange={(e) => setForm((s) => ({ ...s, company: e.target.value }))} placeholder="企业名称" />
              <Input value={form.reg_no} onChange={(e) => setForm((s) => ({ ...s, reg_no: e.target.value }))} placeholder="注册证号" />
              <Select value={form.status} onChange={(e) => setForm((s) => ({ ...s, status: e.target.value }))}>
                <option value="">全部状态</option>
                <option value="active">active</option>
                <option value="cancelled">cancelled</option>
                <option value="expired">expired</option>
              </Select>
            </div>
          ) : null}
        </div>

        <div className="card" style={{ display: 'grid', gap: 10 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 10 }}>
            <strong>口径筛选</strong>
            <Button type="button" size="sm" variant="ghost" onClick={() => setOpenScope((v) => !v)}>
              {openScope ? '折叠' : '展开'}
            </Button>
          </div>
          {openScope ? (
            <div className="controls">
              <Select value={form.sort_by} onChange={(e) => setForm((s) => ({ ...s, sort_by: e.target.value }))}>
                <option value="updated_at">最近更新</option>
                <option value="approved_date">批准日期</option>
                <option value="expiry_date">失效日期</option>
                <option value="name">产品名称</option>
              </Select>
              <Select value={form.sort_order} onChange={(e) => setForm((s) => ({ ...s, sort_order: e.target.value }))}>
                <option value="desc">降序</option>
                <option value="asc">升序</option>
              </Select>
              <label style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <input
                  type="checkbox"
                  checked={form.include_pending}
                  onChange={(e) => setForm((s) => ({ ...s, include_pending: e.target.checked }))}
                />
                <span>包含待核验</span>
              </label>
            </div>
          ) : null}
        </div>

        <div className="card" style={{ display: 'grid', gap: 10, opacity: 0.78 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 10 }}>
            <strong>风险筛选</strong>
            <Button type="button" size="sm" variant="ghost" onClick={() => setOpenRisk((v) => !v)}>
              {openRisk ? '折叠' : '展开'}
            </Button>
          </div>
          {openRisk ? (
            <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
              <Badge variant="muted">{riskHint}</Badge>
              <span className="muted">风险筛选后端未接入</span>
            </div>
          ) : null}
        </div>

        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
          <Button type="submit">查询</Button>
        </div>
      </form>
    </div>
  );
}
