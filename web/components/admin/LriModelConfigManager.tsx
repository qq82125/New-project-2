'use client';

import { useMemo, useState } from 'react';

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card';
import { Input } from '../ui/input';
import { Textarea } from '../ui/textarea';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import { toast } from '../ui/use-toast';
import { ErrorState } from '../States';

type AdminConfigItem = {
  config_key: string;
  config_value: any;
  updated_at: string;
};

type ApiResp<T> = { code: number; message: string; data: T };

type LriConfigShape = {
  model_version: string;
  tte_bins: any[];
  rh_bins: any[];
  cd_bins: any[];
  gp_bins: any[];
  risk_levels: any[];
};

type ComputeResult = {
  ok: boolean;
  dry_run: boolean;
  date: string;
  model_version: string;
  upsert_mode: boolean;
  would_write: number;
  wrote: number;
  risk_dist: Record<string, number>;
  missing_methodology_ratio: number;
  error?: string | null;
};

function parseJsonArray(input: string, field: string): any[] {
  const s = (input || '').trim();
  if (!s) return [];
  let v: any;
  try {
    v = JSON.parse(s);
  } catch (e) {
    throw new Error(`${field} 不是合法 JSON`);
  }
  if (!Array.isArray(v)) throw new Error(`${field} 必须是 JSON 数组`);
  return v;
}

function pretty(v: any): string {
  try {
    return JSON.stringify(v ?? null, null, 2);
  } catch {
    return '';
  }
}

function todayUtc(): string {
  const d = new Date();
  const yyyy = d.getUTCFullYear();
  const mm = String(d.getUTCMonth() + 1).padStart(2, '0');
  const dd = String(d.getUTCDate()).padStart(2, '0');
  return `${yyyy}-${mm}-${dd}`;
}

export default function LriModelConfigManager({ initialConfig }: { initialConfig: AdminConfigItem | null }) {
  const initialValue = useMemo(() => {
    const base = (initialConfig?.config_value && typeof initialConfig.config_value === 'object') ? initialConfig.config_value : {};
    return {
      model_version: String(base.model_version || 'lri_v1'),
      tte_bins: Array.isArray(base.tte_bins) ? base.tte_bins : [],
      rh_bins: Array.isArray(base.rh_bins) ? base.rh_bins : [],
      cd_bins: Array.isArray(base.cd_bins) ? base.cd_bins : [],
      gp_bins: Array.isArray(base.gp_bins) ? base.gp_bins : [],
      risk_levels: Array.isArray(base.risk_levels) ? base.risk_levels : [],
    } satisfies LriConfigShape;
  }, [initialConfig]);

  const [form, setForm] = useState<LriConfigShape>(initialValue);
  const [tteText, setTteText] = useState<string>(pretty(initialValue.tte_bins));
  const [rhText, setRhText] = useState<string>(pretty(initialValue.rh_bins));
  const [cdText, setCdText] = useState<string>(pretty(initialValue.cd_bins));
  const [gpText, setGpText] = useState<string>(pretty(initialValue.gp_bins));
  const [riskText, setRiskText] = useState<string>(pretty(initialValue.risk_levels));
  const [saving, setSaving] = useState(false);
  const [computing, setComputing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [computeDate, setComputeDate] = useState<string>(todayUtc());
  const [lastCompute, setLastCompute] = useState<ComputeResult | null>(null);

  function reset() {
    setForm(initialValue);
    setTteText(pretty(initialValue.tte_bins));
    setRhText(pretty(initialValue.rh_bins));
    setCdText(pretty(initialValue.cd_bins));
    setGpText(pretty(initialValue.gp_bins));
    setRiskText(pretty(initialValue.risk_levels));
    setError(null);
    setLastCompute(null);
    toast({ title: '已重置', description: '已恢复为当前数据库里的值（未保存）。' });
  }

  async function save() {
    if (saving) return;
    const mv = (form.model_version || '').trim();
    if (!mv) {
      toast({ variant: 'destructive', title: '保存失败', description: 'model_version 不能为空' });
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const tte_bins = parseJsonArray(tteText, 'tte_bins');
      const rh_bins = parseJsonArray(rhText, 'rh_bins');
      const cd_bins = parseJsonArray(cdText, 'cd_bins');
      const gp_bins = parseJsonArray(gpText, 'gp_bins');
      const risk_levels = parseJsonArray(riskText, 'risk_levels');

      // Keep other keys intact to avoid breaking nightly flags/max_raw_total, etc.
      const base = (initialConfig?.config_value && typeof initialConfig.config_value === 'object') ? initialConfig.config_value : {};
      const config_value = {
        ...base,
        model_version: mv,
        tte_bins,
        rh_bins,
        cd_bins,
        gp_bins,
        risk_levels,
      };

      const res = await fetch('/api/admin/configs/lri_v1_config', {
        method: 'PUT',
        credentials: 'include',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ config_value }),
      });

      const text = await res.text();
      let parsed: any = null;
      try {
        parsed = JSON.parse(text);
      } catch {
        parsed = null;
      }
      if (!res.ok) {
        const msg = parsed?.detail || parsed?.message || `保存失败 (${res.status})`;
        setError(String(msg));
        toast({ variant: 'destructive', title: '保存失败', description: String(msg) });
        return;
      }
      const body = parsed as ApiResp<AdminConfigItem> | null;
      if (!body || body.code !== 0) {
        const msg = body?.message || '接口返回异常';
        setError(msg);
        toast({ variant: 'destructive', title: '保存失败', description: msg });
        return;
      }

      setForm((p) => ({ ...p, model_version: mv }));
      toast({ title: '已保存', description: `已写回 admin_configs['lri_v1_config']（model_version=${mv}）。` });
    } catch (e) {
      const msg = e instanceof Error ? e.message : '网络错误';
      setError(msg);
      toast({ variant: 'destructive', title: '保存失败', description: msg });
    } finally {
      setSaving(false);
    }
  }

  async function computeNow() {
    if (computing) return;
    const mv = (form.model_version || '').trim() || 'lri_v1';
    const d = (computeDate || '').trim();
    setComputing(true);
    setError(null);
    setLastCompute(null);
    try {
      const res = await fetch('/api/admin/lri/compute', {
        method: 'POST',
        credentials: 'include',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ date: d || null, model_version: mv, upsert: true }),
      });
      const text = await res.text();
      let parsed: any = null;
      try {
        parsed = JSON.parse(text);
      } catch {
        parsed = null;
      }
      if (!res.ok) {
        const msg = parsed?.detail || parsed?.message || `重算失败 (${res.status})`;
        setError(String(msg));
        toast({ variant: 'destructive', title: '重算失败', description: String(msg) });
        return;
      }
      const body = parsed as ApiResp<ComputeResult> | null;
      if (!body || body.code !== 0) {
        const msg = body?.message || '接口返回异常';
        setError(msg);
        toast({ variant: 'destructive', title: '重算失败', description: msg });
        return;
      }
      setLastCompute(body.data);
      toast({ title: '已触发重算', description: `写入 ${body.data.wrote} 条（date=${body.data.date}）。` });
    } catch (e) {
      const msg = e instanceof Error ? e.message : '网络错误';
      setError(msg);
      toast({ variant: 'destructive', title: '重算失败', description: msg });
    } finally {
      setComputing(false);
    }
  }

  const cliHint = useMemo(() => {
    const mv = (form.model_version || '').trim() || 'lri_v1';
    const d = (computeDate || '').trim() || todayUtc();
    return `python -m app.workers.cli lri-compute --date ${d} --execute --upsert --model-version ${mv}`;
  }, [form.model_version, computeDate]);

  return (
    <div className="grid" style={{ gap: 14 }}>
      <Card>
        <CardHeader>
          <CardTitle>LRI V1 配置</CardTitle>
          <CardDescription>编辑 JSON 数组并保存。分段格式示例：{"{"}"lte": 30, "score": 45, "label": "0-30d"{"}"}。</CardDescription>
        </CardHeader>
        <CardContent className="grid" style={{ gap: 10 }}>
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
            <Badge variant="muted">config_key: lri_v1_config</Badge>
            <Badge variant="muted">保存会覆盖对应字段</Badge>
            <Badge variant="muted">重算建议使用 upsert</Badge>
          </div>

          {error ? <ErrorState text={error} /> : null}

          <div className="grid" style={{ gap: 6 }}>
            <div className="muted">model_version</div>
            <Input
              value={form.model_version}
              onChange={(e) => setForm((p) => ({ ...p, model_version: e.target.value }))}
              placeholder="lri_v1"
              disabled={saving || computing}
            />
          </div>

          <div className="grid" style={{ gap: 8 }}>
            <div className="muted">tte_bins (JSON 数组)</div>
            <Textarea rows={6} value={tteText} onChange={(e) => setTteText(e.target.value)} disabled={saving || computing} />
          </div>

          <div className="grid" style={{ gap: 8 }}>
            <div className="muted">rh_bins (JSON 数组)</div>
            <Textarea rows={6} value={rhText} onChange={(e) => setRhText(e.target.value)} disabled={saving || computing} />
          </div>

          <div className="grid" style={{ gap: 8 }}>
            <div className="muted">cd_bins (JSON 数组)</div>
            <Textarea rows={6} value={cdText} onChange={(e) => setCdText(e.target.value)} disabled={saving || computing} />
          </div>

          <div className="grid" style={{ gap: 8 }}>
            <div className="muted">gp_bins (JSON 数组)</div>
            <Textarea rows={6} value={gpText} onChange={(e) => setGpText(e.target.value)} disabled={saving || computing} />
          </div>

          <div className="grid" style={{ gap: 8 }}>
            <div className="muted">risk_levels (JSON 数组)</div>
            <Textarea rows={6} value={riskText} onChange={(e) => setRiskText(e.target.value)} disabled={saving || computing} />
          </div>

          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
            <Button onClick={save} disabled={saving || computing}>
              {saving ? '保存中...' : '保存'}
            </Button>
            <Button variant="secondary" onClick={reset} disabled={saving || computing}>
              重置
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>触发重算</CardTitle>
          <CardDescription>推荐使用接口触发；如接口不可用，可使用下方 CLI 命令手动执行。</CardDescription>
        </CardHeader>
        <CardContent className="grid" style={{ gap: 10 }}>
          <div className="grid" style={{ gap: 6 }}>
            <div className="muted">计算日期 (UTC, YYYY-MM-DD)</div>
            <Input value={computeDate} onChange={(e) => setComputeDate(e.target.value)} placeholder={todayUtc()} disabled={computing || saving} />
          </div>

          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
            <Button onClick={computeNow} disabled={computing || saving}>
              {computing ? '计算中...' : '一键重算 (upsert)'}
            </Button>
            <Badge variant="muted">CLI: {cliHint}</Badge>
          </div>

          {lastCompute ? (
            <Card>
              <CardHeader>
                <CardTitle>重算结果</CardTitle>
                <CardDescription>可用于对比保存前后的风险分布变化。</CardDescription>
              </CardHeader>
              <CardContent className="grid" style={{ gap: 6 }}>
                <div className="muted">date: {lastCompute.date} · model_version: {lastCompute.model_version}</div>
                <div>写入: {lastCompute.wrote} (候选 {lastCompute.would_write})</div>
                <div>缺方法学比例: {(Number(lastCompute.missing_methodology_ratio || 0) * 100).toFixed(1)}%</div>
                <div className="muted">risk_dist: {pretty(lastCompute.risk_dist)}</div>
              </CardContent>
            </Card>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}

