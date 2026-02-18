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
import { RUN_STATUS_ZH, SOURCE_TYPE_ZH, labelFrom } from '../../constants/display';

type DataSource = {
  id: number | null;
  source_key: string;
  entity_scope?: string;
  name: string;
  type: string;
  is_active: boolean;
  enabled: boolean;
  updated_at: string;
  compat?: {
    bound?: boolean;
    mode?: string;
    legacy_name?: string;
    legacy_type?: string;
    legacy_exists?: boolean;
    legacy_data_source_id?: number | null;
    legacy_is_active?: boolean;
  } | null;
  config_preview: {
    folder?: string | null;
    ingest_new?: boolean;
    ingest_chunk_size?: number;
    host: string;
    port: number;
    database: string;
    username: string;
    sslmode?: string | null;
    source_table?: string | null;
    source_query?: string | null;
  };
};

type SourceRegistryItem = {
  source_key: string;
  display_name: string;
  entity_scope: string;
  parser_key: string;
  enabled_by_default: boolean;
  config: {
    id?: string | null;
    enabled?: boolean;
    schedule_cron?: string | null;
    fetch_params?: Record<string, unknown>;
    parse_params?: Record<string, unknown>;
    upsert_policy?: Record<string, unknown>;
    updated_at?: string | null;
  };
  compat?: DataSource['compat'];
};

type ApiResp<T> = { code: number; message: string; data: T };

type LegacyDataSource = {
  id: number;
  name: string;
  type: string;
  is_active: boolean;
  updated_at: string;
  config_preview: DataSource['config_preview'];
};
type ListData = { items: LegacyDataSource[] };
type RegistryListData = { items: SourceRegistryItem[] };
type SourceAuditReport = {
  generated_at?: string;
  upstream?: { filename?: string | null; md5?: string | null; download_url?: string | null } | null;
  upstream_error?: string | null;
  latest_run?: { id?: number; status?: string; started_at?: string | null; finished_at?: string | null } | null;
  freshness?: { hours_since_last_run?: number | null; is_recent_24h?: boolean } | null;
  package_match?: { same_filename?: boolean | null; same_md5?: boolean | null } | null;
  coverage?: {
    total_products?: number;
    missing_reg_no?: number;
    missing_udi_di?: number;
    updated_last_24h?: number;
  } | null;
};
type SupplementSchedule = {
  enabled: boolean;
  interval_hours: number;
  batch_size: number;
  recent_hours: number;
  source_key?: string | null;
  source_name?: string | null;
  nmpa_query_enabled: boolean;
  nmpa_query_interval_hours: number;
  nmpa_query_batch_size: number;
  nmpa_query_url?: string | null;
  nmpa_query_timeout_seconds: number;
};
type SupplementReport = {
  status?: string;
  started_at?: string;
  finished_at?: string;
  scanned?: number;
  matched?: number;
  updated?: number;
  missing_local?: number;
  message?: string;
  source_name?: string | null;
};
type NmpaQueryReport = {
  status?: string;
  started_at?: string;
  finished_at?: string;
  scanned?: number;
  matched?: number;
  updated?: number;
  blocked_412?: number;
  message?: string;
  query_url?: string | null;
};
type DataQualitySample = {
  id: string;
  registration_id?: string | null;
  name: string;
  udi_di?: string | null;
  reg_no?: string | null;
  class_name?: string | null;
  ivd_category?: string | null;
  updated_at?: string | null;
};
type DataQualityReport = {
  generated_at?: string;
  sample_limit?: number;
  counters?: {
    total_ivd?: number;
    name_blank?: number;
    name_punct_only?: number;
    name_placeholder?: number;
    name_too_short?: number;
    reg_no_placeholder?: number;
    class_missing?: number;
    company_missing?: number;
    registration_id_missing?: number;
    reg_no_missing_or_placeholder?: number;
    anchor_both_missing?: number;
  };
  samples?: {
    name_blank?: DataQualitySample[];
    name_punct_only?: DataQualitySample[];
    name_placeholder?: DataQualitySample[];
    name_too_short?: DataQualitySample[];
    reg_no_placeholder?: DataQualitySample[];
    class_missing?: DataQualitySample[];
    company_missing?: DataQualitySample[];
    registration_id_missing?: DataQualitySample[];
    reg_no_missing_or_placeholder?: DataQualitySample[];
    anchor_both_missing?: DataQualitySample[];
  };
};
type ContractBySource = {
  source: string;
  evidence_grade: string;
  source_priority: number;
  applied_changes?: number;
  rejected_changes?: number;
  changed_fields_total?: number;
};
type ContractByDay = {
  date: string;
  applied_changes: number;
  rejected_changes: number;
};
type ContractConflictReport = {
  date?: string | null;
  since?: string | null;
  window_start?: string;
  window_end?: string;
  totals?: {
    total?: number;
    created?: number;
    updated?: number;
    changed_fields_total?: number;
    rejected_total?: number;
  };
  by_source?: ContractBySource[];
  rejected_by_source?: ContractBySource[];
  by_day?: ContractByDay[];
};

async function readErrorDetail(resp: Response): Promise<string | null> {
  try {
    const body = (await resp.json()) as { detail?: string };
    return body?.detail || null;
  } catch {
    return null;
  }
}

type FormState = {
  source_key: string;
  name: string;
  type: 'postgres' | 'local_registry';
  enabled: boolean;
  display_name: string;
  entity_scope: string;
  parser_key: string;
  folder: string;
  ingest_new: boolean;
  ingest_chunk_size: string;
  host: string;
  port: string;
  database: string;
  username: string;
  password: string;
  sslmode: string;
  source_table: string;
  source_query: string;
};

function initialForm(): FormState {
  return {
    source_key: '',
    name: '',
    type: 'postgres',
    enabled: true,
    display_name: '',
    entity_scope: 'REGISTRATION',
    parser_key: '',
    folder: '',
    ingest_new: true,
    ingest_chunk_size: '2000',
    host: '',
    port: '5432',
    database: '',
    username: '',
    password: '',
    sslmode: 'disable',
    source_table: 'public.products',
    source_query: '',
  };
}

function toDataSource(item: SourceRegistryItem): DataSource {
  const fp = (item.config?.fetch_params || {}) as Record<string, unknown>;
  const legacy = (fp.legacy_data_source || {}) as Record<string, unknown>;
  const legacyCfg = (legacy.config || fp.connection || {}) as Record<string, unknown>;
  const t = String(legacy.type || item.compat?.legacy_type || 'postgres');
  const type = t === 'local_registry' ? 'local_registry' : 'postgres';
  return {
    id: item.compat?.legacy_data_source_id ?? null,
    source_key: item.source_key,
    entity_scope: item.entity_scope,
    name: String(legacy.name || item.display_name || item.source_key),
    type,
    is_active: Boolean(item.compat?.legacy_is_active),
    enabled: Boolean(item.config?.enabled ?? item.enabled_by_default),
    updated_at: String(item.config?.updated_at || ''),
    compat: item.compat || null,
    config_preview: {
      folder: typeof legacyCfg.folder === 'string' ? legacyCfg.folder : '',
      ingest_new: legacyCfg.ingest_new !== false,
      ingest_chunk_size: Number(legacyCfg.ingest_chunk_size || 2000),
      host: String(legacyCfg.host || ''),
      port: Number(legacyCfg.port || 5432),
      database: String(legacyCfg.database || ''),
      username: String(legacyCfg.username || ''),
      sslmode: (legacyCfg.sslmode ? String(legacyCfg.sslmode) : null),
      source_table: (legacyCfg.source_table ? String(legacyCfg.source_table) : 'public.products'),
      source_query: (legacyCfg.source_query ? String(legacyCfg.source_query) : null),
    },
  };
}

export default function DataSourcesManager({
  initialItems,
  initialSourceKey,
}: {
  initialItems: DataSource[];
  initialSourceKey?: string;
}) {
  const [items, setItems] = useState<DataSource[]>(initialItems);
  const [sourceKeyFilter, setSourceKeyFilter] = useState<string>(String(initialSourceKey || '').trim().toUpperCase());
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [auditLoading, setAuditLoading] = useState(false);
  const [auditReport, setAuditReport] = useState<SourceAuditReport | null>(null);
  const [qualityLoading, setQualityLoading] = useState(false);
  const [qualityReport, setQualityReport] = useState<DataQualityReport | null>(null);
  const [supplementLoading, setSupplementLoading] = useState(false);
  const [supplementReport, setSupplementReport] = useState<SupplementReport | null>(null);
  const [nmpaQueryReport, setNmpaQueryReport] = useState<NmpaQueryReport | null>(null);
  const [contractLoading, setContractLoading] = useState(false);
  const [contractSinceDays, setContractSinceDays] = useState<number>(7);
  const [contractReport, setContractReport] = useState<ContractConflictReport | null>(null);
  const [supplementSchedule, setSupplementSchedule] = useState<SupplementSchedule>({
    enabled: false,
    interval_hours: 24,
    batch_size: 1000,
    recent_hours: 72,
    source_key: 'UDI_DI',
    source_name: 'UDI补充数据源（规格/DI/包装/GTIN）',
    nmpa_query_enabled: true,
    nmpa_query_interval_hours: 24,
    nmpa_query_batch_size: 200,
    nmpa_query_url: 'https://www.nmpa.gov.cn/datasearch/home-index.html?itemId=2c9ba384759c957701759ccef50f032b#category=ylqx',
    nmpa_query_timeout_seconds: 20,
  });

  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<FormState>(initialForm());

  const editing = useMemo(() => items.find((x) => x.source_key === editingId) || null, [items, editingId]);
  const grouped = useMemo(() => {
    const main = items.filter((x) => (x.compat?.mode || '').toLowerCase() === 'primary' || x.source_key === 'NMPA_REG');
    const project = items.filter((x) => (x.entity_scope || '').toUpperCase() === 'PROCUREMENT' || x.source_key.startsWith('PROCUREMENT_'));
    const mainKeys = new Set(main.map((x) => x.source_key));
    const projectKeys = new Set(project.map((x) => x.source_key));
    const enhance = items.filter((x) => !mainKeys.has(x.source_key) && !projectKeys.has(x.source_key));
    return { main, enhance, project };
  }, [items]);
  const targetSourceKey = useMemo(() => String(initialSourceKey || '').trim().toUpperCase(), [initialSourceKey]);
  const filteredItems = useMemo(() => {
    const key = String(sourceKeyFilter || '').trim().toUpperCase();
    if (!key) return items;
    return items.filter((x) => String(x.source_key || '').toUpperCase().includes(key));
  }, [items, sourceKeyFilter]);
  const targetMatched = useMemo(
    () => (targetSourceKey ? items.some((x) => x.source_key === targetSourceKey) : false),
    [items, targetSourceKey],
  );
  const mainSource = useMemo(
    () =>
      items.find((x) => x.source_key === 'NMPA_REG') ||
      items.find((x) => (x.compat?.mode || '').toLowerCase() === 'primary') ||
      null,
    [items],
  );
  const supplementSources = useMemo(
    () =>
      items.filter(
        (x) =>
          x.source_key !== 'NMPA_REG' &&
          (x.source_key === 'UDI_DI' ||
            (x.entity_scope || '').toUpperCase() === 'UDI' ||
            (x.compat?.mode || '').toLowerCase() === 'supplement'),
      ),
    [items],
  );
  const selectedSupplementSource = useMemo(() => {
    const key = String(supplementSchedule.source_key || '').trim().toUpperCase();
    if (key) {
      const found = supplementSources.find((x) => x.source_key === key);
      if (found) return found;
    }
    const name = String(supplementSchedule.source_name || '').trim();
    if (name) {
      const found = supplementSources.find((x) => x.name === name);
      if (found) return found;
    }
    return supplementSources[0] || null;
  }, [supplementSchedule.source_key, supplementSchedule.source_name, supplementSources]);
  const supplementStatus = (supplementReport?.status || '').toLowerCase();

  async function refresh() {
    setLoading(true);
    setError(null);
    try {
      const regRes = await fetch(`/api/admin/sources`, { credentials: 'include', cache: 'no-store' });
      if (regRes.ok) {
        const regBody = (await regRes.json()) as ApiResp<RegistryListData>;
        if (regBody.code === 0) {
          setItems((regBody.data.items || []).map(toDataSource));
          return;
        }
      }

      // Fallback to legacy API for compatibility.
      const res = await fetch(`/api/admin/data-sources`, { credentials: 'include', cache: 'no-store' });
      if (!res.ok) {
        setError(`加载失败 (${res.status})`);
        return;
      }
      const body = (await res.json()) as ApiResp<ListData>;
      if (body.code !== 0) {
        setError(body.message || '接口返回异常');
        return;
      }
      setItems(
        (body.data.items || []).map((x) => ({
          id: x.id,
          source_key: `LEGACY_${x.id}`,
          entity_scope: 'LEGACY',
          name: x.name,
          type: x.type,
          is_active: Boolean(x.is_active),
          enabled: Boolean(x.is_active),
          updated_at: x.updated_at,
          compat: {
            bound: true,
            mode: 'legacy',
            legacy_name: x.name,
            legacy_type: x.type,
            legacy_exists: true,
            legacy_data_source_id: x.id,
            legacy_is_active: x.is_active,
          },
          config_preview: x.config_preview,
        })),
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : '网络错误');
    } finally {
      setLoading(false);
    }
  }

  async function refreshAudit() {
    setAuditLoading(true);
    try {
      const res = await fetch(`/api/admin/source-audit/last`, { credentials: 'include', cache: 'no-store' });
      if (!res.ok) return;
      const body = (await res.json()) as ApiResp<{ report: SourceAuditReport | null }>;
      if (body.code !== 0) return;
      setAuditReport(body.data?.report || null);
    } catch {
      // keep silent to avoid blocking data-source operations
    } finally {
      setAuditLoading(false);
    }
  }

  async function runAudit() {
    setAuditLoading(true);
    try {
      const res = await fetch(`/api/admin/source-audit/run`, {
        method: 'POST',
        credentials: 'include',
      });
      if (!res.ok) {
        toast({ variant: 'destructive', title: '校验失败', description: `请求失败 (${res.status})` });
        return;
      }
      const body = (await res.json()) as ApiResp<{ report: SourceAuditReport }>;
      if (body.code !== 0) {
        toast({ variant: 'destructive', title: '校验失败', description: body.message || '接口返回异常' });
        return;
      }
      setAuditReport(body.data?.report || null);
      toast({ title: '校验完成', description: '已刷新上游一致性与覆盖率信息' });
    } catch (e) {
      const msg = e instanceof Error ? e.message : '网络错误';
      toast({ variant: 'destructive', title: '网络错误', description: msg });
    } finally {
      setAuditLoading(false);
    }
  }

  async function refreshDataQuality() {
    setQualityLoading(true);
    try {
      const res = await fetch(`/api/admin/data-quality/last`, { credentials: 'include', cache: 'no-store' });
      if (!res.ok) return;
      const body = (await res.json()) as ApiResp<{ report: DataQualityReport | null }>;
      if (body.code !== 0) return;
      setQualityReport(body.data?.report || null);
    } catch {
      // no-op
    } finally {
      setQualityLoading(false);
    }
  }

  async function runDataQuality() {
    setQualityLoading(true);
    try {
      const res = await fetch(`/api/admin/data-quality/run?sample_limit=20`, {
        method: 'POST',
        credentials: 'include',
      });
      if (!res.ok) {
        toast({ variant: 'destructive', title: '质检失败', description: `请求失败 (${res.status})` });
        return;
      }
      const body = (await res.json()) as ApiResp<{ report: DataQualityReport }>;
      if (body.code !== 0) {
        toast({ variant: 'destructive', title: '质检失败', description: body.message || '接口返回异常' });
        return;
      }
      setQualityReport(body.data?.report || null);
      toast({ title: '质检完成', description: '已刷新异常数据统计与样例' });
    } catch (e) {
      const msg = e instanceof Error ? e.message : '网络错误';
      toast({ variant: 'destructive', title: '网络错误', description: msg });
    } finally {
      setQualityLoading(false);
    }
  }

  async function refreshSupplement() {
    setSupplementLoading(true);
    try {
      const [lastRes, nmpaLastRes, confRes] = await Promise.all([
        fetch(`/api/admin/source-supplement/last`, { credentials: 'include', cache: 'no-store' }),
        fetch(`/api/admin/source-nmpa-query/last`, { credentials: 'include', cache: 'no-store' }),
        fetch(`/api/admin/configs`, { credentials: 'include', cache: 'no-store' }),
      ]);
      if (lastRes.ok) {
        const body = (await lastRes.json()) as ApiResp<{ report: SupplementReport | null }>;
        if (body.code === 0) {
          setSupplementReport(body.data?.report || null);
        }
      }
      if (nmpaLastRes.ok) {
        const bodyQ = (await nmpaLastRes.json()) as ApiResp<{ report: NmpaQueryReport | null }>;
        if (bodyQ.code === 0) {
          setNmpaQueryReport(bodyQ.data?.report || null);
        }
      }
      if (confRes.ok) {
        const body = (await confRes.json()) as ApiResp<{ items: Array<{ config_key: string; config_value: unknown }> }>;
        if (body.code === 0) {
          const cfg = body.data?.items?.find((x) => x.config_key === 'source_supplement_schedule')?.config_value;
          if (cfg && typeof cfg === 'object') {
            const raw = cfg as Record<string, unknown>;
            setSupplementSchedule((prev) => ({
              ...prev,
              enabled: Boolean(raw.enabled),
              interval_hours: Number(raw.interval_hours || prev.interval_hours || 24),
              batch_size: Number(raw.batch_size || prev.batch_size || 1000),
              recent_hours: Number(raw.recent_hours || prev.recent_hours || 72),
              source_key: String(raw.source_key || prev.source_key || 'UDI_DI'),
              source_name: String(raw.source_name || prev.source_name || 'UDI补充数据源（规格/DI/包装/GTIN）'),
              nmpa_query_enabled: Boolean(raw.nmpa_query_enabled ?? prev.nmpa_query_enabled),
              nmpa_query_interval_hours: Number(raw.nmpa_query_interval_hours || prev.nmpa_query_interval_hours || 24),
              nmpa_query_batch_size: Number(raw.nmpa_query_batch_size || prev.nmpa_query_batch_size || 200),
              nmpa_query_url: String(raw.nmpa_query_url || prev.nmpa_query_url || ''),
              nmpa_query_timeout_seconds: Number(raw.nmpa_query_timeout_seconds || prev.nmpa_query_timeout_seconds || 20),
            }));
          }
        }
      }
    } catch {
      // no-op
    } finally {
      setSupplementLoading(false);
    }
  }

  async function refreshContractConflicts(days: number = contractSinceDays) {
    setContractLoading(true);
    try {
      const since = new Date();
      since.setDate(since.getDate() - Math.max(0, Number(days || 0)));
      const sinceText = since.toISOString().slice(0, 10);
      const res = await fetch(`/api/admin/source-contract/conflicts?since=${encodeURIComponent(sinceText)}`, {
        credentials: 'include',
        cache: 'no-store',
      });
      if (!res.ok) return;
      const body = (await res.json()) as ApiResp<{ report: ContractConflictReport }>;
      if (body.code !== 0) return;
      setContractReport(body.data?.report || null);
    } catch {
      // no-op
    } finally {
      setContractLoading(false);
    }
  }

  async function saveSupplementSchedule() {
    setSupplementLoading(true);
    try {
      const res = await fetch(`/api/admin/configs/source_supplement_schedule`, {
        method: 'PUT',
        headers: { 'content-type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          config_value: {
            enabled: supplementSchedule.enabled,
            interval_hours: Math.max(1, Number(supplementSchedule.interval_hours || 24)),
            batch_size: Math.max(50, Number(supplementSchedule.batch_size || 1000)),
            recent_hours: Math.max(1, Number(supplementSchedule.recent_hours || 72)),
            source_key: selectedSupplementSource?.source_key || supplementSchedule.source_key || 'UDI_DI',
            source_name: selectedSupplementSource?.name || supplementSchedule.source_name || 'UDI注册证关联增强源（DI/GTIN/包装）',
            nmpa_query_enabled: supplementSchedule.nmpa_query_enabled,
            nmpa_query_interval_hours: Math.max(1, Number(supplementSchedule.nmpa_query_interval_hours || 24)),
            nmpa_query_batch_size: Math.max(10, Number(supplementSchedule.nmpa_query_batch_size || 200)),
            nmpa_query_url:
              supplementSchedule.nmpa_query_url ||
              'https://www.nmpa.gov.cn/datasearch/home-index.html?itemId=2c9ba384759c957701759ccef50f032b#category=ylqx',
            nmpa_query_timeout_seconds: Math.max(5, Number(supplementSchedule.nmpa_query_timeout_seconds || 20)),
          },
        }),
      });
      if (!res.ok) {
        toast({ variant: 'destructive', title: '保存失败', description: `请求失败 (${res.status})` });
        return;
      }
      const body = (await res.json()) as ApiResp<unknown>;
      if (body.code !== 0) {
        toast({ variant: 'destructive', title: '保存失败', description: body.message || '接口返回异常' });
        return;
      }
      toast({ title: '已保存', description: '补充源自动任务配置已更新' });
      await refreshSupplement();
    } catch (e) {
      const msg = e instanceof Error ? e.message : '网络错误';
      toast({ variant: 'destructive', title: '网络错误', description: msg });
    } finally {
      setSupplementLoading(false);
    }
  }

  async function runSupplement() {
    setSupplementLoading(true);
    try {
      const res = await fetch(`/api/admin/source-supplement/run`, {
        method: 'POST',
        credentials: 'include',
      });
      if (!res.ok) {
        toast({ variant: 'destructive', title: '执行失败', description: `请求失败 (${res.status})` });
        return;
      }
      const body = (await res.json()) as ApiResp<{ report: SupplementReport }>;
      if (body.code !== 0) {
        toast({ variant: 'destructive', title: '执行失败', description: body.message || '接口返回异常' });
        return;
      }
      setSupplementReport(body.data?.report || null);
      toast({ title: '已执行', description: '补充源补全任务完成' });
    } catch (e) {
      const msg = e instanceof Error ? e.message : '网络错误';
      toast({ variant: 'destructive', title: '网络错误', description: msg });
    } finally {
      setSupplementLoading(false);
    }
  }

  async function runNmpaQuerySupplement() {
    setSupplementLoading(true);
    try {
      const res = await fetch(`/api/admin/source-nmpa-query/run`, {
        method: 'POST',
        credentials: 'include',
      });
      if (!res.ok) {
        toast({ variant: 'destructive', title: '执行失败', description: `请求失败 (${res.status})` });
        return;
      }
      const body = (await res.json()) as ApiResp<{ report: NmpaQueryReport }>;
      if (body.code !== 0) {
        toast({ variant: 'destructive', title: '执行失败', description: body.message || '接口返回异常' });
        return;
      }
      setNmpaQueryReport(body.data?.report || null);
      toast({ title: '已执行', description: 'NMPA 查询补充任务完成' });
    } catch (e) {
      const msg = e instanceof Error ? e.message : '网络错误';
      toast({ variant: 'destructive', title: '网络错误', description: msg });
    } finally {
      setSupplementLoading(false);
    }
  }

  useEffect(() => {
    // Keep list fresh when entering /admin, but avoid flicker if server already rendered data.
    void refresh();
    void refreshAudit();
    void refreshDataQuality();
    void refreshSupplement();
    void refreshContractConflicts(7);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const key = String(initialSourceKey || '').trim().toUpperCase();
    if (!key) return;
    setSourceKeyFilter(key);
  }, [initialSourceKey]);

  useEffect(() => {
    if (!targetSourceKey) return;
    const row = document.getElementById(`source-row-${targetSourceKey}`);
    if (!row) return;
    row.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }, [items, targetSourceKey]);

  function startCreate() {
    setEditingId(null);
    setForm(initialForm());
  }

  function startEdit(ds: DataSource) {
    setEditingId(ds.source_key);
    setForm({
      source_key: ds.source_key,
      name: ds.name,
      type: (ds.type === 'local_registry' ? 'local_registry' : 'postgres'),
      enabled: ds.enabled,
      display_name: ds.name,
      entity_scope: 'REGISTRATION',
      parser_key: '',
      folder: ds.config_preview.folder || '',
      ingest_new: ds.config_preview.ingest_new !== false,
      ingest_chunk_size: String(ds.config_preview.ingest_chunk_size || 2000),
      host: ds.config_preview.host,
      port: String(ds.config_preview.port || 5432),
      database: ds.config_preview.database,
      username: ds.config_preview.username,
      password: '', // never show existing password
      sslmode: (ds.config_preview.sslmode || 'disable') as string,
      source_table: ds.config_preview.source_table || 'public.products',
      source_query: ds.config_preview.source_query || '',
    });
  }

  async function save() {
    setLoading(true);
    setError(null);
    try {
      const port = Number(form.port || '5432');
      const isEdit = editingId != null;
      const sourceKey = form.source_key.trim().toUpperCase();
      if (!sourceKey) {
        setError('source_key 不能为空');
        return;
      }
      const role = sourceKey === 'NMPA_REG' ? 'primary' : 'supplement';
      const legacyConfig =
        form.type === 'local_registry'
          ? {
              folder: form.folder.trim(),
              ingest_new: form.ingest_new,
              ingest_chunk_size: Number(form.ingest_chunk_size || '2000'),
            }
          : {
              host: form.host,
              port,
              database: form.database,
              username: form.username,
              ...(form.password ? { password: form.password } : {}),
              sslmode: form.sslmode || null,
              source_table: form.source_table || 'public.products',
              ...(form.source_query.trim() ? { source_query: form.source_query.trim() } : {}),
            };
      const payload = {
        source_key: sourceKey,
        ...(isEdit
          ? {}
          : {
              display_name: form.display_name.trim() || form.name.trim() || sourceKey,
              entity_scope: form.entity_scope.trim().toUpperCase() || 'REGISTRATION',
              parser_key: form.parser_key.trim() || sourceKey.toLowerCase(),
              enabled_by_default: true,
            }),
        enabled: form.enabled,
        fetch_params: {
          legacy_data_source: {
            name: form.name.trim() || form.display_name.trim() || sourceKey,
            type: form.type,
            role,
            config: legacyConfig,
          },
        },
      };

      const resp = await fetch(`/api/admin/sources`, {
        method: isEdit ? 'PATCH' : 'POST',
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
      const body = (await resp.json()) as ApiResp<unknown>;
      if (body.code !== 0) {
        const msg = body.message || '接口返回异常';
        setError(msg);
        toast({ variant: 'destructive', title: '保存失败', description: msg });
        return;
      }
      toast({ title: '保存成功', description: isEdit ? `已更新数据源 ${editingId}` : '已创建数据源' });
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

  async function testConnection(ds: DataSource) {
    const legacyId = ds.compat?.legacy_data_source_id;
    if (!legacyId) {
      toast({ variant: 'destructive', title: '无法测试', description: '该来源未绑定 legacy data source。' });
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const resp = await fetch(`/api/admin/data-sources/${legacyId}/test`, {
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
        toast({ title: '连接成功', description: `${ds.name}` });
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

  async function activate(sourceKey: string) {
    setLoading(true);
    setError(null);
    try {
      const resp = await fetch(`/api/admin/sources`, {
        method: 'PATCH',
        headers: { 'content-type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ source_key: sourceKey, enabled: true }),
      });
      if (!resp.ok) {
        const msg = `激活失败 (${resp.status})`;
        setError(msg);
        toast({ variant: 'destructive', title: '激活失败', description: msg });
        return;
      }
      const body = (await resp.json()) as ApiResp<unknown>;
      if (body.code !== 0) {
        const msg = body.message || '接口返回异常';
        setError(msg);
        toast({ variant: 'destructive', title: '激活失败', description: msg });
        return;
      }
      toast({ title: '已设为启用', description: sourceKey });
      await refresh();
    } catch (e) {
      const msg = e instanceof Error ? e.message : '网络错误';
      setError(msg);
      toast({ variant: 'destructive', title: '网络错误', description: msg });
    } finally {
      setLoading(false);
    }
  }

  async function remove(sourceKey: string) {
    const ds = items.find((x) => x.source_key === sourceKey);
    if (!ds) return;
    if (!window.confirm(`确认停用数据源「${ds.name}」(${ds.source_key}) 吗？`)) return;

    setLoading(true);
    setError(null);
    try {
      const resp = await fetch(`/api/admin/sources`, {
        method: 'PATCH',
        headers: { 'content-type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ source_key: sourceKey, enabled: false }),
      });
      if (!resp.ok) {
        const detail = await readErrorDetail(resp);
        const msg = detail ? `${detail} (${resp.status})` : `停用失败 (${resp.status})`;
        setError(msg);
        toast({ variant: 'destructive', title: '停用失败', description: msg });
        return;
      }
      const body = (await resp.json()) as ApiResp<unknown>;
      if (body.code !== 0) {
        const msg = body.message || '停用失败';
        setError(msg);
        toast({ variant: 'destructive', title: '停用失败', description: msg });
        return;
      }
      toast({ title: '已停用', description: sourceKey });
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
          <CardTitle>主源校验状态（{mainSource?.name || 'NMPA注册产品库（主数据源）'}）</CardTitle>
          <CardDescription>展示主数据源上游包一致性、近 24 小时新鲜度与主库覆盖率。</CardDescription>
        </CardHeader>
        <CardContent className="grid" style={{ gap: 10 }}>
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
            <Button variant="secondary" onClick={runAudit} disabled={auditLoading || loading}>
              {auditLoading ? '校验中...' : '立即校验'}
            </Button>
            <Badge variant={auditReport?.freshness?.is_recent_24h ? 'success' : 'warning'}>
              新鲜度: {auditReport?.freshness?.is_recent_24h ? '24h 内' : '超 24h / 未知'}
            </Badge>
            <Badge
              variant={
                auditReport?.package_match?.same_filename === true && auditReport?.package_match?.same_md5 !== false
                  ? 'success'
                  : 'warning'
              }
            >
              主源包: {auditReport?.package_match?.same_filename ? '已匹配' : '待核对'}
            </Badge>
            <Badge variant={mainSource?.enabled ? 'success' : 'warning'}>
              主源配置: {mainSource?.enabled ? '已启用' : '未启用'}
            </Badge>
          </div>

          {!auditReport ? (
            <EmptyState text="暂无校验结果，点击“立即校验”获取最新状态。" />
          ) : (
            <div className="columns-3">
              <div className="card">
                <div className="muted">最近校验</div>
                <div>{auditReport.generated_at ? new Date(auditReport.generated_at).toLocaleString() : '-'}</div>
                <div className="muted" style={{ marginTop: 6 }}>
                  最近运行间隔: {auditReport.freshness?.hours_since_last_run ?? '-'} 小时
                </div>
              </div>
              <div className="card">
                <div className="muted">覆盖率</div>
                <div>产品总数: {auditReport.coverage?.total_products ?? 0}</div>
                <div>24h 更新: {auditReport.coverage?.updated_last_24h ?? 0}</div>
                <div className="muted">缺失 reg_no: {auditReport.coverage?.missing_reg_no ?? 0}</div>
              </div>
              <div className="card">
                <div className="muted">主源上游包</div>
                <div className="muted" style={{ fontSize: 12, wordBreak: 'break-all' }}>
                  {auditReport.upstream?.filename || '-'}
                </div>
                <div className="muted" style={{ marginTop: 6 }}>
                  MD5: {auditReport.upstream?.md5 || '-'}
                </div>
                {auditReport.upstream_error ? (
                  <div className="muted" style={{ color: 'var(--danger)', marginTop: 6 }}>
                    上游错误: {auditReport.upstream_error}
                  </div>
                ) : null}
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>补充源自动任务</CardTitle>
          <CardDescription>用于 UDI 增强源纠错/回溯补全，仅填充主源空字段，不覆盖已有值。</CardDescription>
        </CardHeader>
        <CardContent className="grid" style={{ gap: 10 }}>
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
            <Badge variant={supplementSchedule.enabled ? 'success' : 'muted'}>
              自动任务: {supplementSchedule.enabled ? '已启用' : '未启用'}
            </Badge>
            <Badge variant="muted">间隔: {supplementSchedule.interval_hours}h</Badge>
            <Badge variant="muted">批量: {supplementSchedule.batch_size}</Badge>
            <Badge variant="muted">增强源: {selectedSupplementSource?.name || supplementSchedule.source_name || '-'}</Badge>
            <Badge variant={supplementSchedule.nmpa_query_enabled ? 'success' : 'muted'}>
              NMPA查询补充: {supplementSchedule.nmpa_query_enabled ? '已启用' : '未启用'}
            </Badge>
          </div>
          <div className="controls">
            <Select
              value={supplementSchedule.enabled ? 'on' : 'off'}
              onChange={(e) => setSupplementSchedule((p) => ({ ...p, enabled: e.target.value === 'on' }))}
            >
              <option value="on">自动任务开启</option>
              <option value="off">自动任务关闭</option>
            </Select>
            <Input
              value={String(supplementSchedule.interval_hours)}
              onChange={(e) => setSupplementSchedule((p) => ({ ...p, interval_hours: Number(e.target.value || 24) }))}
              placeholder="间隔小时"
              inputMode="numeric"
            />
            <Input
              value={String(supplementSchedule.batch_size)}
              onChange={(e) => setSupplementSchedule((p) => ({ ...p, batch_size: Number(e.target.value || 1000) }))}
              placeholder="批量"
              inputMode="numeric"
            />
            <Input
              value={String(supplementSchedule.recent_hours)}
              onChange={(e) => setSupplementSchedule((p) => ({ ...p, recent_hours: Number(e.target.value || 72) }))}
              placeholder="回溯小时"
              inputMode="numeric"
            />
            <Select
              value={(selectedSupplementSource?.source_key || supplementSchedule.source_key || 'UDI_DI').toString()}
              onChange={(e) => {
                const key = e.target.value;
                const src = supplementSources.find((x) => x.source_key === key) || null;
                setSupplementSchedule((p) => ({
                  ...p,
                  source_key: key,
                  source_name: src?.name || p.source_name,
                }));
              }}
            >
              {(supplementSources.length > 0
                ? supplementSources
                : ([{ source_key: 'UDI_DI', name: 'UDI注册证关联增强源（DI/GTIN/包装）' }] as Array<
                    Pick<DataSource, 'source_key' | 'name'>
                  >)
              ).map((s) => (
                <option key={s.source_key} value={s.source_key}>
                  {s.name}
                </option>
              ))}
            </Select>
            <Select
              value={supplementSchedule.nmpa_query_enabled ? 'on' : 'off'}
              onChange={(e) => setSupplementSchedule((p) => ({ ...p, nmpa_query_enabled: e.target.value === 'on' }))}
            >
              <option value="on">NMPA 查询补充开启</option>
              <option value="off">NMPA 查询补充关闭</option>
            </Select>
            <Input
              value={String(supplementSchedule.nmpa_query_interval_hours)}
              onChange={(e) => setSupplementSchedule((p) => ({ ...p, nmpa_query_interval_hours: Number(e.target.value || 24) }))}
              placeholder="NMPA间隔小时"
              inputMode="numeric"
            />
            <Input
              value={String(supplementSchedule.nmpa_query_batch_size)}
              onChange={(e) => setSupplementSchedule((p) => ({ ...p, nmpa_query_batch_size: Number(e.target.value || 200) }))}
              placeholder="NMPA批量"
              inputMode="numeric"
            />
            <Input
              value={String(supplementSchedule.nmpa_query_timeout_seconds)}
              onChange={(e) => setSupplementSchedule((p) => ({ ...p, nmpa_query_timeout_seconds: Number(e.target.value || 20) }))}
              placeholder="NMPA超时秒"
              inputMode="numeric"
            />
            <Input
              value={supplementSchedule.nmpa_query_url || ''}
              onChange={(e) => setSupplementSchedule((p) => ({ ...p, nmpa_query_url: e.target.value }))}
              placeholder="NMPA 查询地址（选填）"
            />
          </div>
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
            <Button onClick={saveSupplementSchedule} disabled={supplementLoading || loading}>
              保存自动任务
            </Button>
            <Button variant="secondary" onClick={runSupplement} disabled={supplementLoading || loading}>
              {supplementLoading ? '执行中...' : '立即执行补全'}
            </Button>
            <Button variant="secondary" onClick={runNmpaQuerySupplement} disabled={supplementLoading || loading}>
              {supplementLoading ? '执行中...' : '立即执行NMPA查询补充'}
            </Button>
          </div>
          {supplementReport ? (
            <div className="card">
              <div className="muted">
                最近执行: {supplementReport.finished_at ? new Date(supplementReport.finished_at).toLocaleString() : '-'}
              </div>
              <div>
                状态: {labelFrom(RUN_STATUS_ZH, supplementStatus)}，扫描 {supplementReport.scanned ?? 0}，补全{' '}
                {supplementReport.updated ?? 0}，未命中本地 {supplementReport.missing_local ?? 0}
              </div>
              {supplementReport.message ? <div className="muted">{supplementReport.message}</div> : null}
            </div>
          ) : (
            <EmptyState text="暂无补充源执行记录" />
          )}
          {nmpaQueryReport ? (
            <div className="card">
              <div className="muted">
                NMPA查询最近执行: {nmpaQueryReport.finished_at ? new Date(nmpaQueryReport.finished_at).toLocaleString() : '-'}
              </div>
              <div>
                状态: {labelFrom(RUN_STATUS_ZH, (nmpaQueryReport.status || '').toLowerCase())}，扫描{' '}
                {nmpaQueryReport.scanned ?? 0}，命中 {nmpaQueryReport.matched ?? 0}，补全 {nmpaQueryReport.updated ?? 0}，412阻断{' '}
                {nmpaQueryReport.blocked_412 ?? 0}
              </div>
              {nmpaQueryReport.message ? <div className="muted">{nmpaQueryReport.message}</div> : null}
            </div>
          ) : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Source Contract 冲突统计</CardTitle>
          <CardDescription>展示 registration_no 冲突决策采纳/拒绝结果（evidence_grade + source_priority + observed_at）。</CardDescription>
        </CardHeader>
        <CardContent className="grid" style={{ gap: 10 }}>
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
            <Select
              value={String(contractSinceDays)}
              onChange={(e) => setContractSinceDays(Number(e.target.value || 7))}
            >
              <option value="1">近 1 天</option>
              <option value="3">近 3 天</option>
              <option value="7">近 7 天</option>
              <option value="30">近 30 天</option>
            </Select>
            <Button variant="secondary" onClick={() => void refreshContractConflicts(contractSinceDays)} disabled={contractLoading || loading}>
              {contractLoading ? '加载中...' : '刷新统计'}
            </Button>
            <Badge variant="muted">采纳: {contractReport?.totals?.total ?? 0}</Badge>
            <Badge variant="warning">拒绝: {contractReport?.totals?.rejected_total ?? 0}</Badge>
          </div>

          {contractReport ? (
            <div className="columns-3">
              <div className="card">
                <div className="muted">窗口</div>
                <div style={{ fontSize: 12 }}>{contractReport.window_start || '-'}</div>
                <div style={{ fontSize: 12 }}>{contractReport.window_end || '-'}</div>
              </div>
              <div className="card">
                <div className="muted">采纳统计</div>
                <div>创建: {contractReport.totals?.created ?? 0}</div>
                <div>更新: {contractReport.totals?.updated ?? 0}</div>
                <div className="muted">字段变更: {contractReport.totals?.changed_fields_total ?? 0}</div>
              </div>
              <div className="card">
                <div className="muted">趋势(按天)</div>
                {(contractReport.by_day || []).slice(-5).map((x) => (
                  <div key={x.date} style={{ fontSize: 12 }}>
                    {x.date}: 采纳 {x.applied_changes} / 拒绝 {x.rejected_changes}
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <EmptyState text="暂无冲突统计数据" />
          )}

          {(contractReport?.by_source || []).length > 0 ? (
            <TableWrap>
              <Table>
                <thead>
                  <tr>
                    <th>来源</th>
                    <th>证据等级</th>
                    <th>优先级</th>
                    <th>采纳</th>
                    <th>字段变更</th>
                  </tr>
                </thead>
                <tbody>
                  {(contractReport?.by_source || []).slice(0, 8).map((r, i) => (
                    <tr key={`${r.source}-${r.evidence_grade}-${i}`}>
                      <td>{r.source}</td>
                      <td>{r.evidence_grade}</td>
                      <td>{String(r.source_priority)}</td>
                      <td>{String(r.applied_changes ?? 0)}</td>
                      <td>{String(r.changed_fields_total ?? 0)}</td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            </TableWrap>
          ) : null}
          {(contractReport?.rejected_by_source || []).length > 0 ? (
            <TableWrap>
              <Table>
                <thead>
                  <tr>
                    <th>来源</th>
                    <th>证据等级</th>
                    <th>优先级</th>
                    <th>拒绝次数</th>
                  </tr>
                </thead>
                <tbody>
                  {(contractReport?.rejected_by_source || []).slice(0, 8).map((r, i) => (
                    <tr key={`${r.source}-${r.evidence_grade}-rej-${i}`}>
                      <td>{r.source}</td>
                      <td>{r.evidence_grade}</td>
                      <td>{String(r.source_priority)}</td>
                      <td>{String(r.rejected_changes ?? 0)}</td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            </TableWrap>
          ) : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>数据质检与锚点健康（IVD）</CardTitle>
          <CardDescription>检查名称异常 + 注册锚点完整性（registration_id/reg_no）+ 企业与分类缺失。</CardDescription>
        </CardHeader>
        <CardContent className="grid" style={{ gap: 10 }}>
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
            <Button variant="secondary" onClick={runDataQuality} disabled={qualityLoading || loading}>
              {qualityLoading ? '质检中...' : '立即质检'}
            </Button>
            <Badge variant="muted">IVD总量: {qualityReport?.counters?.total_ivd ?? 0}</Badge>
            <Badge variant={(qualityReport?.counters?.anchor_both_missing || 0) > 0 ? 'warning' : 'success'}>
              锚点双缺失: {qualityReport?.counters?.anchor_both_missing ?? 0}
            </Badge>
            <Badge variant={(qualityReport?.counters?.registration_id_missing || 0) > 0 ? 'warning' : 'success'}>
              registration_id缺失: {qualityReport?.counters?.registration_id_missing ?? 0}
            </Badge>
            <Badge variant={(qualityReport?.counters?.reg_no_missing_or_placeholder || 0) > 0 ? 'warning' : 'success'}>
              reg_no缺失/占位: {qualityReport?.counters?.reg_no_missing_or_placeholder ?? 0}
            </Badge>
            <Badge variant={(qualityReport?.counters?.company_missing || 0) > 0 ? 'warning' : 'success'}>
              企业缺失: {qualityReport?.counters?.company_missing ?? 0}
            </Badge>
            <Badge variant="muted">主源: {mainSource?.name || '-'}</Badge>
            <Badge variant="muted">增强源: {selectedSupplementSource?.name || '-'}</Badge>
          </div>

          {!qualityReport ? (
            <EmptyState text="暂无质检结果，点击“立即质检”获取最新数据质量报告。" />
          ) : (
            <>
              <div className="card">
                <div className="muted">最近质检</div>
                <div>{qualityReport.generated_at ? new Date(qualityReport.generated_at).toLocaleString() : '-'}</div>
                <div className="muted" style={{ marginTop: 6 }}>
                  样例上限: {qualityReport.sample_limit ?? 20} 条/项
                </div>
                <div style={{ marginTop: 8 }}>
                  分类缺失: {qualityReport.counters?.class_missing ?? 0}，企业缺失: {qualityReport.counters?.company_missing ?? 0}
                </div>
                <div className="muted" style={{ marginTop: 8 }}>
                  锚点建议优先修复: `anchor_both_missing` → `registration_id_missing` → `company_missing`
                </div>
              </div>
              {(qualityReport.samples?.anchor_both_missing || []).length > 0 ? (
                <div className="card">
                  <div className="muted">异常样例（注册锚点双缺失）</div>
                  <div className="list" style={{ marginTop: 8 }}>
                    {(qualityReport.samples?.anchor_both_missing || []).slice(0, 5).map((it) => (
                      <div key={it.id} className="muted" style={{ wordBreak: 'break-all' }}>
                        {it.name} | UDI-DI: {it.udi_di || '-'} | reg_no: {it.reg_no || '-'} | registration_id:{' '}
                        {it.registration_id || '-'}
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <EmptyState text="当前未发现“注册锚点双缺失”异常样例。" />
              )}
            </>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>数据源管理</CardTitle>
          <CardDescription>统一管理主源、增强源、项目源。新增来源可直接配置启用。</CardDescription>
        </CardHeader>
        <CardContent className="grid">
          <div className="controls">
            <Input
              value={form.source_key}
              onChange={(e) => setForm((p) => ({ ...p, source_key: e.target.value.toUpperCase() }))}
              placeholder="来源编码（必填，例如 NMPA_REG / UDI_DI）"
              disabled={editingId != null}
            />
            <Input
              value={form.display_name}
              onChange={(e) => setForm((p) => ({ ...p, display_name: e.target.value }))}
              placeholder="展示名称（必填，用于页面展示）"
            />
            <Input
              value={form.parser_key}
              onChange={(e) => setForm((p) => ({ ...p, parser_key: e.target.value }))}
              placeholder="解析器标识（必填，对应后端解析器）"
            />
            <Select
              value={form.entity_scope}
              onChange={(e) => setForm((p) => ({ ...p, entity_scope: e.target.value }))}
            >
              <option value="REGISTRATION">注册证</option>
              <option value="UDI">UDI 标识</option>
              <option value="PROCUREMENT">招采数据</option>
              <option value="NHSA">国家医保</option>
            </Select>
            <Input
              value={form.name}
              onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))}
              placeholder="连接名称（建议填写，兼容旧链路）"
            />
            <Select
              value={form.type}
              onChange={(e) => setForm((p) => ({ ...p, type: e.target.value as 'postgres' | 'local_registry' }))}
            >
              <option value="postgres">PostgreSQL 数据库</option>
              <option value="local_registry">本地注册库目录</option>
            </Select>
            <Select
              value={form.enabled ? 'yes' : 'no'}
              onChange={(e) => setForm((p) => ({ ...p, enabled: e.target.value === 'yes' }))}
            >
              <option value="yes">启用</option>
              <option value="no">停用</option>
            </Select>
            {form.type === 'local_registry' ? (
              <>
                <Input
                  value={form.folder}
                  onChange={(e) => setForm((p) => ({ ...p, folder: e.target.value }))}
                  placeholder="目录路径（必填，需包含 .xlsx/.zip 文件）"
                />
                <Select
                  value={form.ingest_new ? 'yes' : 'no'}
                  onChange={(e) => setForm((p) => ({ ...p, ingest_new: e.target.value === 'yes' }))}
                >
                  <option value="yes">导入新产品（推荐）</option>
                  <option value="no">仅补全已有产品</option>
                </Select>
                <Input
                  value={form.ingest_chunk_size}
                  onChange={(e) => setForm((p) => ({ ...p, ingest_chunk_size: e.target.value }))}
                  placeholder="导入批量（选填，默认 2000）"
                  inputMode="numeric"
                />
              </>
            ) : (
              <>
                <Input
                  value={form.host}
                  onChange={(e) => setForm((p) => ({ ...p, host: e.target.value }))}
                  placeholder="主机地址（必填，例如 127.0.0.1）"
                />
                <Input
                  value={form.port}
                  onChange={(e) => setForm((p) => ({ ...p, port: e.target.value }))}
                  placeholder="端口（必填，例如 5432）"
                  inputMode="numeric"
                />
                <Input
                  value={form.database}
                  onChange={(e) => setForm((p) => ({ ...p, database: e.target.value }))}
                  placeholder="数据库名（必填）"
                />
                <Input
                  value={form.username}
                  onChange={(e) => setForm((p) => ({ ...p, username: e.target.value }))}
                  placeholder="用户名（必填）"
                />
                <Input
                  value={form.password}
                  onChange={(e) => setForm((p) => ({ ...p, password: e.target.value }))}
                  placeholder={editing ? '密码（留空表示不修改）' : '密码（必填）'}
                  type="password"
                />
                <Select value={form.sslmode} onChange={(e) => setForm((p) => ({ ...p, sslmode: e.target.value }))}>
                  <option value="disable">SSL 关闭（disable）</option>
                  <option value="prefer">SSL 优先（prefer）</option>
                  <option value="require">SSL 必须（require）</option>
                </Select>
                <Input
                  value={form.source_table}
                  onChange={(e) => setForm((p) => ({ ...p, source_table: e.target.value }))}
                  placeholder="主源表（选填，默认 public.products）"
                />
                <Input
                  value={form.source_query}
                  onChange={(e) => setForm((p) => ({ ...p, source_query: e.target.value }))}
                  placeholder="主源 SQL（选填，优先于主源表）"
                />
              </>
            )}
          </div>

          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
            <Button onClick={save} disabled={loading}>
              {editingId ? `保存编辑 ${editingId}` : '新增来源配置'}
            </Button>
            <Button variant="secondary" onClick={startCreate} disabled={loading}>
              清空表单
            </Button>
            {editingId ? (
              <Badge variant="muted">正在编辑：{editing?.name || editingId}</Badge>
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
          <CardDescription>展示 Source Registry 配置状态；主源是否 Active 见“主源Active”标记。</CardDescription>
        </CardHeader>
        <CardContent>
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 12 }}>
            <Badge variant="success">主源 {grouped.main.length}</Badge>
            <Badge variant="muted">增强源 {grouped.enhance.length}</Badge>
            <Badge variant="warning">项目源 {grouped.project.length}</Badge>
            {targetSourceKey ? (
              <Badge variant={targetMatched ? 'success' : 'warning'}>
                定位来源: {targetSourceKey} {targetMatched ? '已匹配' : '未找到'}
              </Badge>
            ) : null}
          </div>
          <div className="controls" style={{ marginBottom: 12 }}>
            <Input
              value={sourceKeyFilter}
              onChange={(e) => setSourceKeyFilter(e.target.value.toUpperCase())}
              placeholder="按 source_key 过滤（如 NMPA_REG / UDI_DI）"
            />
            <Button
              variant="secondary"
              onClick={() => setSourceKeyFilter('')}
              disabled={!sourceKeyFilter}
            >
              清除过滤
            </Button>
          </div>
          {loading && items.length === 0 ? (
            <div className="grid">
              <Skeleton height={28} />
              <Skeleton height={180} />
            </div>
          ) : filteredItems.length === 0 ? (
            <EmptyState text="暂无数据源" />
          ) : (
            <TableWrap>
              <Table>
                <thead>
                  <tr>
                    <th>分组</th>
                    <th>名称</th>
                    <th>类型</th>
                    <th>连接</th>
                    <th style={{ width: 110 }}>状态</th>
                    <th style={{ width: 260 }}>操作</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredItems.map((ds) => (
                    <tr
                      key={ds.source_key}
                      id={`source-row-${ds.source_key}`}
                      style={
                        targetSourceKey && ds.source_key === targetSourceKey
                          ? { backgroundColor: 'rgba(16, 185, 129, 0.08)', outline: '1px solid rgba(16, 185, 129, 0.45)' }
                          : undefined
                      }
                    >
                      <td>
                        {(ds.compat?.mode || '').toLowerCase() === 'primary' || ds.source_key === 'NMPA_REG'
                          ? '主源'
                          : (ds.entity_scope || '').toUpperCase() === 'PROCUREMENT' || ds.source_key.startsWith('PROCUREMENT_')
                            ? '项目源'
                            : '增强源'}
                      </td>
                      <td>
                        <strong>{ds.name}</strong>
                        <div className="muted" style={{ fontSize: 12 }}>{ds.source_key}</div>
                      </td>
                      <td>{labelFrom(SOURCE_TYPE_ZH, ds.type)}</td>
                      <td>
                        {ds.type === 'local_registry' ? (
                          <>
                            <div>
                              <span className="muted">目录:</span> {ds.config_preview.folder || '-'}
                            </div>
                            <div>
                              <span className="muted">导入新产品:</span> {ds.config_preview.ingest_new === false ? '否' : '是'}
                              {'  '}
                              <span className="muted">批量:</span> {ds.config_preview.ingest_chunk_size || 2000}
                            </div>
                          </>
                        ) : (
                          <>
                            <div>
                              <span className="muted">主机:</span> {ds.config_preview.host}:{ds.config_preview.port}
                            </div>
                            <div>
                              <span className="muted">数据库:</span> {ds.config_preview.database}{' '}
                              <span className="muted">用户:</span> {ds.config_preview.username}
                            </div>
                            <div>
                              <span className="muted">主源表:</span> {ds.config_preview.source_table || 'public.products'}
                            </div>
                            {ds.config_preview.source_query ? (
                              <div className="muted" style={{ fontSize: 12, wordBreak: 'break-all' }}>
                                <span className="muted">主源SQL:</span> {ds.config_preview.source_query}
                              </div>
                            ) : null}
                          </>
                        )}
                      </td>
                      <td>
                        {ds.enabled ? <Badge variant="success">已启用</Badge> : <Badge variant="muted">未启用</Badge>}
                        {ds.is_active ? <Badge variant="muted">主源Active</Badge> : null}
                      </td>
                      <td>
                        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                          <Button size="sm" variant="secondary" onClick={() => startEdit(ds)} disabled={loading}>
                            编辑
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => testConnection(ds)}
                            disabled={loading || !ds.compat?.legacy_data_source_id}
                          >
                            {ds.type === 'local_registry' ? '校验目录' : '测试连接'}
                          </Button>
                          <Button
                            size="sm"
                            variant={ds.enabled ? 'secondary' : 'default'}
                            onClick={() => activate(ds.source_key)}
                            disabled={loading || ds.enabled}
                          >
                            设为启用
                          </Button>
                          <Button
                            size="sm"
                            variant="secondary"
                            onClick={() => remove(ds.source_key)}
                            disabled={loading || !ds.enabled}
                          >
                            停用
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
