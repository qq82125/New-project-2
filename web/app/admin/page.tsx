'use client';

import { useEffect, useMemo, useState } from 'react';

type AdminConfigItem = {
  config_key: string;
  config_value: Record<string, unknown>;
  updated_at: string;
};

type AdminConfigsResponse = {
  code: number;
  message: string;
  data: {
    items: AdminConfigItem[];
  };
};

const API = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
const AUTH_KEY = 'admin_basic_auth';

function toBasicAuth(username: string, password: string): string {
  return `Basic ${btoa(`${username}:${password}`)}`;
}

export default function AdminPage() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [auth, setAuth] = useState('');
  const [items, setItems] = useState<AdminConfigItem[]>([]);
  const [editMap, setEditMap] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const stored = typeof window !== 'undefined' ? localStorage.getItem(AUTH_KEY) : null;
    if (stored) setAuth(stored);
  }, []);

  async function loadConfigs(token?: string) {
    const finalToken = token || auth;
    if (!finalToken) return;
    setLoading(true);
    setError(null);
    setMessage(null);
    try {
      const resp = await fetch(`${API}/api/admin/configs`, {
        headers: { Authorization: finalToken },
        cache: 'no-store',
      });
      if (resp.status === 401) {
        setError('认证失败，请检查管理员账号密码。');
        return;
      }
      if (!resp.ok) {
        setError(`加载失败（${resp.status}）`);
        return;
      }
      const body = (await resp.json()) as AdminConfigsResponse;
      if (body.code !== 0) {
        setError(body.message || '接口返回异常');
        return;
      }
      setItems(body.data.items);
      const initialEditMap: Record<string, string> = {};
      body.data.items.forEach((item) => {
        initialEditMap[item.config_key] = JSON.stringify(item.config_value, null, 2);
      });
      setEditMap(initialEditMap);
    } catch (e) {
      setError(e instanceof Error ? e.message : '网络错误');
    } finally {
      setLoading(false);
    }
  }

  async function login() {
    const token = toBasicAuth(username.trim(), password);
    localStorage.setItem(AUTH_KEY, token);
    setAuth(token);
    await loadConfigs(token);
  }

  function logout() {
    localStorage.removeItem(AUTH_KEY);
    setAuth('');
    setItems([]);
    setEditMap({});
    setMessage('已退出管理员模式。');
  }

  async function saveConfig(configKey: string) {
    const raw = editMap[configKey];
    let parsed: Record<string, unknown>;
    try {
      parsed = JSON.parse(raw);
    } catch {
      setError(`${configKey} 不是合法 JSON`);
      return;
    }
    setLoading(true);
    setError(null);
    setMessage(null);
    try {
      const resp = await fetch(`${API}/api/admin/configs/${encodeURIComponent(configKey)}`, {
        method: 'PUT',
        headers: {
          'content-type': 'application/json',
          Authorization: auth,
        },
        body: JSON.stringify({ config_value: parsed }),
      });
      if (resp.status === 401) {
        setError('认证已失效，请重新登录。');
        return;
      }
      if (!resp.ok) {
        setError(`保存失败（${resp.status}）`);
        return;
      }
      setMessage(`已保存：${configKey}`);
      await loadConfigs();
    } catch (e) {
      setError(e instanceof Error ? e.message : '网络错误');
    } finally {
      setLoading(false);
    }
  }

  const canLoad = useMemo(() => Boolean(auth), [auth]);

  return (
    <div className="grid">
      <section className="card">
        <h2>后台管理</h2>
        {!auth ? (
          <div className="controls">
            <input value={username} onChange={(e) => setUsername(e.target.value)} placeholder="管理员账号" />
            <input
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              type="password"
              placeholder="管理员密码"
            />
            <button onClick={login} disabled={loading}>
              登录
            </button>
          </div>
        ) : (
          <div className="controls">
            <button onClick={() => loadConfigs()} disabled={loading || !canLoad}>
              刷新配置
            </button>
            <button onClick={logout} disabled={loading}>
              退出
            </button>
          </div>
        )}
        {error && <div className="card error">{error}</div>}
        {message && <div className="card">{message}</div>}
      </section>

      {auth &&
        items.map((item) => (
          <section className="card" key={item.config_key}>
            <h3>{item.config_key}</h3>
            <div className="muted">更新时间：{new Date(item.updated_at).toLocaleString()}</div>
            <textarea
              value={editMap[item.config_key] || ''}
              onChange={(e) =>
                setEditMap((prev) => ({
                  ...prev,
                  [item.config_key]: e.target.value,
                }))
              }
              rows={10}
            />
            <button onClick={() => saveConfig(item.config_key)} disabled={loading}>
              保存 {item.config_key}
            </button>
          </section>
        ))}
    </div>
  );
}
