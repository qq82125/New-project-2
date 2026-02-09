'use client';

import { useEffect, useMemo, useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card';
import { Table, TableWrap } from '../ui/table';
import { Input } from '../ui/input';
import { Select } from '../ui/select';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import { Skeleton } from '../ui/skeleton';
import { toast } from '../ui/use-toast';
import { EmptyState, ErrorState } from '../States';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

type DataSource = {
  id: number;
  name: string;
  type: string;
  is_active: boolean;
  updated_at: string;
  config_preview: {
    host: string;
    port: number;
    database: string;
    username: string;
    sslmode?: string | null;
  };
};

type ApiResp<T> = { code: number; message: string; data: T };

type ListData = { items: DataSource[] };

async function readErrorDetail(resp: Response): Promise<string | null> {
  try {
    const body = (await resp.json()) as { detail?: string };
    return body?.detail || null;
  } catch {
    return null;
  }
}

type FormState = {
  name: string;
  type: 'postgres';
  host: string;
  port: string;
  database: string;
  username: string;
  password: string;
  sslmode: string;
};

function initialForm(): FormState {
  return {
    name: '',
    type: 'postgres',
    host: '',
    port: '5432',
    database: '',
    username: '',
    password: '',
    sslmode: 'disable',
  };
}

export default function DataSourcesManager({ initialItems }: { initialItems: DataSource[] }) {
  const [items, setItems] = useState<DataSource[]>(initialItems);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [editingId, setEditingId] = useState<number | null>(null);
  const [form, setForm] = useState<FormState>(initialForm());

  const editing = useMemo(() => items.find((x) => x.id === editingId) || null, [items, editingId]);

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/admin/data-sources`, { credentials: 'include', cache: 'no-store' });
      if (!res.ok) {
        setError(`加载失败 (${res.status})`);
        return;
      }
      const body = (await res.json()) as ApiResp<ListData>;
      if (body.code !== 0) {
        setError(body.message || '接口返回异常');
        return;
      }
      setItems(body.data.items);
    } catch (e) {
      setError(e instanceof Error ? e.message : '网络错误');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    // Keep list fresh when entering /admin, but avoid flicker if server already rendered data.
    void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function startCreate() {
    setEditingId(null);
    setForm(initialForm());
  }

  function startEdit(ds: DataSource) {
    setEditingId(ds.id);
    setForm({
      name: ds.name,
      type: 'postgres',
      host: ds.config_preview.host,
      port: String(ds.config_preview.port || 5432),
      database: ds.config_preview.database,
      username: ds.config_preview.username,
      password: '', // never show existing password
      sslmode: (ds.config_preview.sslmode || 'disable') as string,
    });
  }

  async function save() {
    setLoading(true);
    setError(null);
    try {
      const port = Number(form.port || '5432');
      const isEdit = editingId != null;

      const url = isEdit
        ? `${API_BASE}/api/admin/data-sources/${editingId}`
        : `${API_BASE}/api/admin/data-sources`;

      const method = isEdit ? 'PUT' : 'POST';

      const payload = isEdit
        ? {
            name: form.name,
            config: {
              host: form.host,
              port,
              database: form.database,
              username: form.username,
              ...(form.password ? { password: form.password } : {}),
              sslmode: form.sslmode || null,
            },
          }
        : {
            name: form.name,
            type: form.type,
            config: {
              host: form.host,
              port,
              database: form.database,
              username: form.username,
              password: form.password,
              sslmode: form.sslmode || null,
            },
          };

      const resp = await fetch(url, {
        method,
        headers: { 'content-type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(payload),
      });
      if (!resp.ok) {
        const detail = await readErrorDetail(resp);
        const msg = detail ? `${detail} (${resp.status})` : `保存失败 (${resp.status})`;
        setError(msg);
        toast({ variant: 'destructive', title: '保存失败', description: msg });
        return;
      }
      const body = (await resp.json()) as ApiResp<{ id: number }>;
      if (body.code !== 0) {
        const msg = body.message || '接口返回异常';
        setError(msg);
        toast({ variant: 'destructive', title: '保存失败', description: msg });
        return;
      }
      toast({ title: '保存成功', description: isEdit ? `已更新数据源 #${editingId}` : '已创建数据源' });
      startCreate();
      await refresh();
    } catch (e) {
      const msg = e instanceof Error ? e.message : '网络错误';
      setError(msg);
      toast({ variant: 'destructive', title: '网络错误', description: msg });
    } finally {
      setLoading(false);
    }
  }

  async function testConnection(id: number) {
    setLoading(true);
    setError(null);
    try {
      const resp = await fetch(`${API_BASE}/api/admin/data-sources/${id}/test`, {
        method: 'POST',
        credentials: 'include',
      });
      if (!resp.ok) {
        const msg = `测试失败 (${resp.status})`;
        setError(msg);
        toast({ variant: 'destructive', title: '连接测试失败', description: msg });
        return;
      }
      const body = (await resp.json()) as ApiResp<{ ok: boolean; message: string }>;
      if (body.code !== 0) {
        const msg = body.message || '接口返回异常';
        setError(msg);
        toast({ variant: 'destructive', title: '连接测试失败', description: msg });
        return;
      }
      if (body.data.ok) {
        toast({ title: '连接成功', description: `数据源 #${id}` });
      } else {
        toast({ variant: 'destructive', title: '连接失败', description: body.data.message });
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : '网络错误';
      setError(msg);
      toast({ variant: 'destructive', title: '网络错误', description: msg });
    } finally {
      setLoading(false);
    }
  }

  async function activate(id: number) {
    setLoading(true);
    setError(null);
    try {
      const resp = await fetch(`${API_BASE}/api/admin/data-sources/${id}/activate`, {
        method: 'POST',
        credentials: 'include',
      });
      if (!resp.ok) {
        const msg = `激活失败 (${resp.status})`;
        setError(msg);
        toast({ variant: 'destructive', title: '激活失败', description: msg });
        return;
      }
      const body = (await resp.json()) as ApiResp<{ id: number }>;
      if (body.code !== 0) {
        const msg = body.message || '接口返回异常';
        setError(msg);
        toast({ variant: 'destructive', title: '激活失败', description: msg });
        return;
      }
      toast({ title: '已设为 Active', description: `数据源 #${id}` });
      await refresh();
    } catch (e) {
      const msg = e instanceof Error ? e.message : '网络错误';
      setError(msg);
      toast({ variant: 'destructive', title: '网络错误', description: msg });
    } finally {
      setLoading(false);
    }
  }

  async function remove(id: number) {
    const ds = items.find((x) => x.id === id);
    if (!ds) return;
    if (ds.is_active) {
      toast({ variant: 'destructive', title: '无法删除', description: '请先将其它数据源设为 Active。' });
      return;
    }
    if (!window.confirm(`确认删除数据源「${ds.name}」(#${ds.id}) 吗？此操作不可恢复。`)) return;

    setLoading(true);
    setError(null);
    try {
      const resp = await fetch(`${API_BASE}/api/admin/data-sources/${id}`, {
        method: 'DELETE',
        credentials: 'include',
      });
      if (!resp.ok) {
        const detail = await readErrorDetail(resp);
        const msg = detail ? `${detail} (${resp.status})` : `删除失败 (${resp.status})`;
        setError(msg);
        toast({ variant: 'destructive', title: '删除失败', description: msg });
        return;
      }
      const body = (await resp.json()) as ApiResp<{ deleted: boolean }>;
      if (body.code !== 0 || !body.data?.deleted) {
        const msg = body.message || '删除失败';
        setError(msg);
        toast({ variant: 'destructive', title: '删除失败', description: msg });
        return;
      }
      toast({ title: '已删除', description: `数据源 #${id}` });
      await refresh();
    } catch (e) {
      const msg = e instanceof Error ? e.message : '网络错误';
      setError(msg);
      toast({ variant: 'destructive', title: '网络错误', description: msg });
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="grid">
      <Card>
        <CardHeader>
          <CardTitle>数据源管理</CardTitle>
          <CardDescription>可创建多个数据源；同一时间只能有一个 Active。名称需唯一。密码仅加密存储，不会在界面回显。</CardDescription>
        </CardHeader>
        <CardContent className="grid">
          <div className="controls">
            <Input
              value={form.name}
              onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))}
              placeholder="名称（唯一）"
            />
            <Select value={form.type} onChange={(e) => setForm((p) => ({ ...p, type: e.target.value as 'postgres' }))}>
              <option value="postgres">postgres</option>
            </Select>
            <Input
              value={form.host}
              onChange={(e) => setForm((p) => ({ ...p, host: e.target.value }))}
              placeholder="host"
            />
            <Input
              value={form.port}
              onChange={(e) => setForm((p) => ({ ...p, port: e.target.value }))}
              placeholder="port"
              inputMode="numeric"
            />
            <Input
              value={form.database}
              onChange={(e) => setForm((p) => ({ ...p, database: e.target.value }))}
              placeholder="database"
            />
            <Input
              value={form.username}
              onChange={(e) => setForm((p) => ({ ...p, username: e.target.value }))}
              placeholder="username"
            />
            <Input
              value={form.password}
              onChange={(e) => setForm((p) => ({ ...p, password: e.target.value }))}
              placeholder={editing ? 'password（留空表示不修改）' : 'password'}
              type="password"
            />
            <Select value={form.sslmode} onChange={(e) => setForm((p) => ({ ...p, sslmode: e.target.value }))}>
              <option value="disable">sslmode=disable</option>
              <option value="prefer">sslmode=prefer</option>
              <option value="require">sslmode=require</option>
            </Select>
          </div>

          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
            <Button onClick={save} disabled={loading}>
              {editingId ? `保存编辑 #${editingId}` : '新增数据源'}
            </Button>
            <Button variant="secondary" onClick={startCreate} disabled={loading}>
              清空表单
            </Button>
            {editingId ? (
              <Badge variant="muted">正在编辑：{editing?.name || `#${editingId}`}</Badge>
            ) : (
              <Badge variant="muted">创建新数据源</Badge>
            )}
          </div>

          {error ? <ErrorState text={error} /> : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>数据源列表</CardTitle>
          <CardDescription>只能有一个 Active 数据源。</CardDescription>
        </CardHeader>
        <CardContent>
          {loading && items.length === 0 ? (
            <div className="grid">
              <Skeleton height={28} />
              <Skeleton height={180} />
            </div>
          ) : items.length === 0 ? (
            <EmptyState text="暂无数据源" />
          ) : (
            <TableWrap>
              <Table>
                <thead>
                  <tr>
                    <th>名称</th>
                    <th>类型</th>
                    <th>连接</th>
                    <th style={{ width: 110 }}>状态</th>
                    <th style={{ width: 260 }}>操作</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((ds) => (
                    <tr key={ds.id}>
                      <td>
                        <strong>{ds.name}</strong>
                        <div className="muted" style={{ fontSize: 12 }}>#{ds.id}</div>
                      </td>
                      <td>{ds.type}</td>
                      <td>
                        <div>
                          <span className="muted">host:</span> {ds.config_preview.host}:{ds.config_preview.port}
                        </div>
                        <div>
                          <span className="muted">db:</span> {ds.config_preview.database}{' '}
                          <span className="muted">user:</span> {ds.config_preview.username}
                        </div>
                      </td>
                      <td>
                        {ds.is_active ? <Badge variant="success">ACTIVE</Badge> : <Badge variant="muted">inactive</Badge>}
                      </td>
                      <td>
                        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                          <Button size="sm" variant="secondary" onClick={() => startEdit(ds)} disabled={loading}>
                            编辑
                          </Button>
                          <Button size="sm" variant="ghost" onClick={() => testConnection(ds.id)} disabled={loading}>
                            测试连接
                          </Button>
                          <Button
                            size="sm"
                            variant={ds.is_active ? 'secondary' : 'default'}
                            onClick={() => activate(ds.id)}
                            disabled={loading || ds.is_active}
                          >
                            设为 Active
                          </Button>
                          <Button
                            size="sm"
                            variant="destructive"
                            onClick={() => remove(ds.id)}
                            disabled={loading || ds.is_active}
                          >
                            删除
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            </TableWrap>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
