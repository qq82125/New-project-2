'use client';

import { useMemo, useState } from 'react';

import { EmptyState, ErrorState, LoadingState } from '../States';
import { Badge } from '../ui/badge';
import { Button } from '../ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card';
import { Input } from '../ui/input';
import { Modal } from '../ui/modal';
import { Select } from '../ui/select';
import { Table, TableWrap } from '../ui/table';
import { toast } from '../ui/use-toast';

type SourceItem = {
  source_key: string;
  display_name: string;
  entity_scope: string;
  default_evidence_grade: string;
  parser_key: string;
  enabled_by_default: boolean;
  config: {
    id?: string | null;
    enabled?: boolean;
    schedule_cron?: string | null;
    fetch_params?: Record<string, unknown>;
    parse_params?: Record<string, unknown>;
    upsert_policy?: Record<string, unknown>;
    last_run_at?: string | null;
    last_status?: string | null;
    last_error?: string | null;
    created_at?: string | null;
    updated_at?: string | null;
  };
};

type ListResp = {
  code: number;
  message: string;
  data?: { items: SourceItem[]; count: number };
  detail?: unknown;
};

type PatchResp = {
  code: number;
  message: string;
  data?: { item: SourceItem };
  detail?: unknown;
};

type EditState = {
  source_key: string;
  enabled: boolean;
  schedule_cron: string;
  priority: string;
  parser_key: string;
  default_evidence_grade: string;
  error: string;
};

function parseApiError(body: unknown, fallback: string): string {
  if (!body || typeof body !== 'object') return fallback;
  const obj = body as Record<string, unknown>;
  const code = obj.code ? String(obj.code) : '';
  const msg = obj.message ? String(obj.message) : '';
  const detail = obj.detail;
  if (detail && typeof detail === 'object') {
    const d = detail as Record<string, unknown>;
    const dc = d.code ? String(d.code) : '';
    const dm = d.message ? String(d.message) : '';
    return [dc, dm].filter(Boolean).join(' - ') || [code, msg].filter(Boolean).join(' - ') || fallback;
  }
  if (typeof detail === 'string' && detail.trim()) {
    return [code, msg, detail].filter(Boolean).join(' - ');
  }
  return [code, msg].filter(Boolean).join(' - ') || fallback;
}

export default function SourcesRegistryManager({ initialItems }: { initialItems: SourceItem[] }) {
  const [items, setItems] = useState<SourceItem[]>(initialItems || []);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [query, setQuery] = useState('');
  const [edit, setEdit] = useState<EditState | null>(null);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return items;
    return items.filter((x) => {
      return (
        x.source_key.toLowerCase().includes(q) ||
        x.display_name.toLowerCase().includes(q) ||
        x.entity_scope.toLowerCase().includes(q) ||
        x.parser_key.toLowerCase().includes(q)
      );
    });
  }, [items, query]);

  async function refresh() {
    setLoading(true);
    setError('');
    try {
      const res = await fetch('/api/admin/sources', {
        method: 'GET',
        credentials: 'include',
        cache: 'no-store',
      });
      const body = (await res.json().catch(() => ({}))) as ListResp;
      if (!res.ok || body.code !== 0 || !body.data) {
        throw new Error(parseApiError(body, `HTTP ${res.status}`));
      }
      setItems(body.data.items || []);
    } catch (e) {
      const msg = String((e as Error)?.message || e || '加载失败');
      setError(msg);
      toast({ variant: 'destructive', title: '刷新失败', description: msg });
    } finally {
      setLoading(false);
    }
  }

  function openEditor(row: SourceItem) {
    const parseParams = row.config.parse_params || {};
    const upsertPolicy = row.config.upsert_policy || {};
    const parserOverride = String(parseParams.parser_key || row.parser_key || '').trim();
    const gradeOverride = String(parseParams.default_evidence_grade || row.default_evidence_grade || 'C')
      .trim()
      .toUpperCase();
    const priority = String(upsertPolicy.priority ?? '100');
    setEdit({
      source_key: row.source_key,
      enabled: Boolean(row.config.enabled ?? row.enabled_by_default),
      schedule_cron: String(row.config.schedule_cron || ''),
      priority,
      parser_key: parserOverride,
      default_evidence_grade: ['A', 'B', 'C', 'D'].includes(gradeOverride) ? gradeOverride : 'C',
      error: '',
    });
  }

  async function saveEdit() {
    if (!edit) return;
    const p = Number(edit.priority || '100');
    if (!Number.isFinite(p)) {
      setEdit({ ...edit, error: 'priority 必须是数字' });
      return;
    }
    setLoading(true);
    try {
      const current = items.find((x) => x.source_key === edit.source_key);
      const parse_params = {
        ...(current?.config.parse_params || {}),
        parser_key: edit.parser_key.trim(),
        default_evidence_grade: edit.default_evidence_grade,
      };
      const upsert_policy = {
        ...(current?.config.upsert_policy || {}),
        priority: Math.trunc(p),
      };
      const res = await fetch('/api/admin/sources', {
        method: 'PATCH',
        credentials: 'include',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({
          source_key: edit.source_key,
          enabled: edit.enabled,
          schedule_cron: edit.schedule_cron.trim() || null,
          parse_params,
          upsert_policy,
        }),
      });
      const body = (await res.json().catch(() => ({}))) as PatchResp;
      if (!res.ok || body.code !== 0 || !body.data?.item) {
        const msg = parseApiError(body, `HTTP ${res.status}`);
        setEdit({ ...edit, error: msg });
        toast({ variant: 'destructive', title: '保存失败', description: msg });
        return;
      }
      toast({ title: '保存成功', description: edit.source_key });
      setEdit(null);
      await refresh();
    } catch (e) {
      const msg = String((e as Error)?.message || e || '保存失败');
      setEdit({ ...edit, error: msg });
      toast({ variant: 'destructive', title: '保存失败', description: msg });
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="grid">
      <Card>
        <CardHeader>
          <CardTitle>数据源列表</CardTitle>
          <CardDescription>支持编辑启停、优先级、解析器、默认证据等级与调度周期。</CardDescription>
        </CardHeader>
        <CardContent style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
          <Input
            placeholder="按 source_key / 名称 / 范围 / 解析器 过滤"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            style={{ minWidth: 360 }}
          />
          <Button variant="secondary" onClick={() => void refresh()} disabled={loading}>
            {loading ? '刷新中...' : '刷新'}
          </Button>
          <Badge variant="muted">共 {filtered.length} 条</Badge>
        </CardContent>
        <CardContent>
          {loading && items.length === 0 ? (
            <LoadingState text="正在加载数据源..." />
          ) : error ? (
            <ErrorState text={error} />
          ) : filtered.length === 0 ? (
            <EmptyState text="暂无数据源配置" />
          ) : (
            <TableWrap>
              <Table>
                <thead>
                  <tr>
                    <th>source_key</th>
                    <th>名称</th>
                    <th>数据范围</th>
                    <th>解析器</th>
                    <th>证据等级</th>
                    <th>优先级</th>
                    <th>状态</th>
                    <th>操作</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map((row) => {
                    const priority = Number((row.config.upsert_policy || {}).priority ?? 100);
                    const enabled = Boolean(row.config.enabled ?? row.enabled_by_default);
                    const parserView = String((row.config.parse_params || {}).parser_key || row.parser_key || '-');
                    const gradeView = String((row.config.parse_params || {}).default_evidence_grade || row.default_evidence_grade || 'C');
                    return (
                      <tr key={row.source_key}>
                        <td>{row.source_key}</td>
                        <td>{row.display_name}</td>
                        <td>{row.entity_scope}</td>
                        <td>{parserView}</td>
                        <td>{gradeView}</td>
                        <td>{priority}</td>
                        <td>{enabled ? <Badge variant="success">启用</Badge> : <Badge variant="muted">停用</Badge>}</td>
                        <td>
                          <Button size="sm" onClick={() => openEditor(row)}>
                            编辑
                          </Button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </Table>
            </TableWrap>
          )}
        </CardContent>
      </Card>

      <Modal
        open={!!edit}
        onClose={() => setEdit(null)}
        title="编辑数据源配置"
        footer={
          <div style={{ display: 'flex', gap: 8 }}>
            <Button variant="secondary" onClick={() => setEdit(null)} disabled={loading}>
              取消
            </Button>
            <Button onClick={() => void saveEdit()} disabled={loading}>
              保存
            </Button>
          </div>
        }
      >
        {!edit ? null : (
          <div className="grid" style={{ gap: 10 }}>
            {edit.error ? <ErrorState text={edit.error} /> : null}
            <div>
              <div className="muted">source_key</div>
              <div>{edit.source_key}</div>
            </div>
            <div>
              <div className="muted">启停状态</div>
              <Select
                value={edit.enabled ? 'on' : 'off'}
                onChange={(e) => setEdit({ ...edit, enabled: String(e.target.value) === 'on' })}
              >
                <option value="on">启用</option>
                <option value="off">停用</option>
              </Select>
            </div>
            <div>
              <div className="muted">优先级（upsert_policy.priority）</div>
              <Input
                value={edit.priority}
                onChange={(e) => setEdit({ ...edit, priority: e.target.value })}
                inputMode="numeric"
              />
            </div>
            <div>
              <div className="muted">默认证据等级（parse_params）</div>
              <Select
                value={edit.default_evidence_grade}
                onChange={(e) => setEdit({ ...edit, default_evidence_grade: String(e.target.value).toUpperCase() })}
              >
                <option value="A">A</option>
                <option value="B">B</option>
                <option value="C">C</option>
                <option value="D">D</option>
              </Select>
            </div>
            <div>
              <div className="muted">解析器（parse_params）</div>
              <Input
                value={edit.parser_key}
                onChange={(e) => setEdit({ ...edit, parser_key: e.target.value })}
              />
            </div>
            <div>
              <div className="muted">schedule_cron（可空）</div>
              <Input
                value={edit.schedule_cron}
                onChange={(e) => setEdit({ ...edit, schedule_cron: e.target.value })}
                placeholder="如：0 */6 * * *"
              />
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
