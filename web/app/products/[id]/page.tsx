import { headers } from 'next/headers';
import { redirect } from 'next/navigation';
import Link from 'next/link';
import { EmptyState, ErrorState } from '../../../components/States';
import { apiGet } from '../../../lib/api';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../../../components/ui/card';
import { Badge } from '../../../components/ui/badge';

import { apiBase } from '../../../lib/api-server';
import { getMe } from '../../../lib/getMe';
import ProUpgradeHint from '../../../components/plan/ProUpgradeHint';
import { PRO_COPY, PRO_TRIAL_HREF } from '../../../constants/pro';
import { IVD_CATEGORY_ZH, STATUS_ZH, labelFrom } from '../../../constants/display';
import LriCard from '../../../components/lri/LriCard';
import PackagingTree, { type PackingEdge } from '../../../components/udi/PackagingTree';
import CopyTextButton from '../../../components/detail/CopyTextButton';
import { getRegistrationTimeline } from '../../../lib/api/registrations';
import { ApiHttpError } from '../../../lib/api/client';
import { toChangeRows, toEvidenceRows } from '../../../lib/detail';

type ProductData = {
  id: string;
  name: string;
  reg_no?: string | null;
  registrations?: Array<string | { registration_no?: string | null; reg_no?: string | null }> | null;
  udi_di?: string | null;
  status: string;
  approved_date?: string | null;
  expiry_date?: string | null;
  class_name?: string | null;
  model?: string | null;
  specification?: string | null;
  category?: string | null;
  description?: string | null;
  ivd_category?: string | null;
  company?: { id: string; name: string; country?: string | null } | null;
  is_stub?: boolean | null;
  source_hint?: string | null;
  verified_by_nmpa?: boolean | null;
};

type ProductParamItem = {
  id: string;
  param_code: string;
  value_num?: number | null;
  value_text?: string | null;
  unit?: string | null;
  conditions?: any | null;
  confidence: number;
  evidence_text: string;
  evidence_page?: number | null;
  source?: string | null;
};

type ProductParamsData = {
  product_id: string;
  product_name: string;
  items: ProductParamItem[];
};

type ProductLriScore = {
  registration_id: string;
  product_id?: string | null;
  methodology_code?: string | null;
  methodology_name_cn?: string | null;
  tte_days?: number | null;
  renewal_count?: number | null;
  competitive_count?: number | null;
  gp_new_12m?: number | null;
  tte_score?: number | null;
  rh_score?: number | null;
  cd_score?: number | null;
  gp_score?: number | null;
  lri_total?: number | null;
  lri_norm: number;
  risk_level: string;
  model_version: string;
  calculated_at: string;
};

type ProductLriData = {
  product_id: string;
  registration_id?: string | null;
  score?: ProductLriScore | null;
};

type VariantItem = {
  di: string;
  model_spec?: string | null;
  manufacturer?: string | null;
  packaging_json?: any[] | any | null;
};

type RegistrationData = {
  id: string;
  registration_no: string;
  status?: string | null;
  is_stub?: boolean | null;
  source_hint?: string | null;
  verified_by_nmpa?: boolean | null;
  variants: VariantItem[];
};

function packingsFromPackagingJson(v: any): PackingEdge[] {
  if (!v) return [];
  if (Array.isArray(v)) return v as PackingEdge[];
  if (typeof v === 'object' && Array.isArray((v as any).packings)) return (v as any).packings as PackingEdge[];
  return [];
}

function storagesFromStorageParam(p: ProductParamItem | null | undefined): any[] {
  const c = (p as any)?.conditions;
  if (!c) return [];
  if (Array.isArray((c as any).storages)) return (c as any).storages;
  return [];
}

function firstRegistrationNo(product: ProductData): string | null {
  if (product.reg_no) return product.reg_no;
  const regs = product.registrations || [];
  for (const item of regs) {
    if (typeof item === 'string' && item) return item;
    if (item && typeof item === 'object') {
      if (item.registration_no) return item.registration_no;
      if (item.reg_no) return item.reg_no;
    }
  }
  return null;
}

function isNotFound(err: unknown): boolean {
  return err instanceof ApiHttpError && err.status === 404;
}

function viewText(v: unknown): string {
  if (v === null || v === undefined || v === '') return '-';
  if (typeof v === 'string') return v;
  if (typeof v === 'number' || typeof v === 'boolean') return String(v);
  try {
    return JSON.stringify(v);
  } catch {
    return String(v);
  }
}

function FieldRow({ label, value }: { label: string; value: unknown }) {
  const text = viewText(value);
  const isLong = text.length > 120;
  return (
    <div className="columns-2" style={{ gap: 8 }}>
      <div className="muted">{label}</div>
      <div>
        {isLong ? (
          <details>
            <summary>show more</summary>
            <div style={{ whiteSpace: 'pre-wrap', marginTop: 6 }}>{text}</div>
          </details>
        ) : (
          <span>{text}</span>
        )}
      </div>
    </div>
  );
}

function FieldGroup({ title, rows }: { title: string; rows: Array<{ label: string; value: unknown }> }) {
  return (
    <details className="card" open>
      <summary style={{ cursor: 'pointer', fontWeight: 700 }}>{title}</summary>
      <div className="grid" style={{ marginTop: 10 }}>
        {rows.map((row) => (
          <FieldRow key={row.label} label={row.label} value={row.value} />
        ))}
      </div>
    </details>
  );
}

export default async function ProductDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const API_BASE = apiBase();
  const cookie = (await headers()).get('cookie') || '';
  const meRes = await fetch(`${API_BASE}/api/auth/me`, {
    method: 'GET',
    headers: cookie ? { cookie } : undefined,
    cache: 'no-store',
  });
  if (meRes.status === 401) redirect('/login');
  const me = await getMe();
  const isPro = Boolean(me?.plan?.is_pro || me?.plan?.is_admin);

  const { id } = await params;
  const res = await apiGet<ProductData>(`/api/products/${id}`);
  const paramsRes = isPro ? await apiGet<ProductParamsData>(`/api/products/${id}/params`) : { data: null, error: null, status: null };
  const lriRes = await apiGet<ProductLriData>(`/api/products/${id}/lri`);

  if (res.error) {
    return <ErrorState text={`产品加载失败：${res.error}`} />;
  }
  if (!res.data) {
    return <EmptyState text="产品不存在" />;
  }
  const anchorRegNo = firstRegistrationNo(res.data);

  const regRes =
    anchorRegNo
      ? await apiGet<RegistrationData>(`/api/registrations/${encodeURIComponent(anchorRegNo)}`)
      : { data: null, error: null, status: null };
  const timelineResult = anchorRegNo ? await Promise.resolve(getRegistrationTimeline(anchorRegNo).then((x) => ({ data: x, error: null })).catch((e) => ({ data: null, error: e }))) : { data: [], error: null };
  const timelineNotFound = timelineResult.error ? isNotFound(timelineResult.error) : false;
  const timelineEvents = timelineResult.data || [];
  const evidenceRows = toEvidenceRows(timelineEvents as any);
  const changeRows = toChangeRows(timelineEvents as any).slice(0, 5);
  const latestChangeDate = timelineEvents.length > 0 ? String((timelineEvents[0] as any).observed_at || '-') : '-';

  return (
    <div className="grid">
      <Card>
        <CardHeader>
          <CardTitle>产品详情</CardTitle>
          <CardDescription>概览区</CardDescription>
        </CardHeader>
        <CardContent className="grid">
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
            <Badge variant="muted">产品名: {res.data.name || '-'}</Badge>
            <Badge variant="muted">企业名: {res.data.company?.name || '-'}</Badge>
            <Badge
              variant={
                res.data.status === 'active'
                  ? 'success'
                  : res.data.status === 'expired'
                    ? 'warning'
                    : res.data.status === 'cancelled'
                      ? 'danger'
                    : 'muted'
              }
            >
              状态: {labelFrom(STATUS_ZH, res.data.status) || '-'}
            </Badge>
          </div>
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
            <Badge variant="muted">注册证号: {anchorRegNo || '-'}</Badge>
            {anchorRegNo ? <CopyTextButton value={anchorRegNo} /> : null}
          </div>
          <div className="columns-3">
            <div>
              <div className="muted">批准日期</div>
              <div>{res.data.approved_date || '-'}</div>
            </div>
            <div>
              <div className="muted">变更日期</div>
              <div>{latestChangeDate}</div>
            </div>
            <div>
              <div className="muted">失效日期</div>
              <div>{res.data.expiry_date || '-'}</div>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>结构化字段</CardTitle>
          <CardDescription>字段分组折叠展示</CardDescription>
        </CardHeader>
        <CardContent className="grid">
          <FieldGroup
            title="基本信息"
            rows={[
              { label: '产品名', value: res.data.name },
              { label: '企业名', value: res.data.company?.name || '-' },
              { label: '注册证号', value: anchorRegNo || '-' },
              { label: '状态', value: labelFrom(STATUS_ZH, res.data.status) || '-' },
            ]}
          />
          <FieldGroup
            title="适用范围"
            rows={[
              { label: 'IVD分类', value: labelFrom(IVD_CATEGORY_ZH, res.data.ivd_category) || '-' },
              { label: '分类码', value: res.data.class_name || '-' },
              { label: '类别', value: res.data.category || '-' },
              { label: '产品描述', value: res.data.description || '-' },
            ]}
          />
          <FieldGroup
            title="结构组成"
            rows={[
              { label: '型号', value: res.data.model || '-' },
              { label: '规格', value: res.data.specification || '-' },
              { label: 'UDI-DI', value: res.data.udi_di || '-' },
              { label: 'DI列表', value: regRes.data?.variants?.map((x) => x.di).join(' / ') || '-' },
            ]}
          />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>证据与变更</CardTitle>
          <CardDescription>可解释证据链与最近字段变更</CardDescription>
        </CardHeader>
        <CardContent className="grid">
          {timelineResult.error && !timelineNotFound ? (
            <ErrorState text="加载失败，请重试" />
          ) : (
            <>
              <div className="card">
                <div style={{ fontWeight: 700, marginBottom: 8 }}>证据</div>
                {evidenceRows.length === 0 ? (
                  <EmptyState text="暂无可追溯证据（优先补采 raw_documents）" />
                ) : (
                  <div className="grid">
                    {evidenceRows.slice(0, 8).map((item, idx) => (
                      <div key={`${item.source}-${idx}`} className="card">
                        <div><span className="muted">来源：</span>{item.source || '-'}</div>
                        <div><span className="muted">观察时间：</span>{item.observed_at || '-'}</div>
                        <div>
                          <span className="muted">证据片段：</span>
                          {String(item.excerpt || '').length > 120 ? (
                            <details>
                              <summary>show more</summary>
                              <div style={{ whiteSpace: 'pre-wrap', marginTop: 6 }}>{item.excerpt}</div>
                            </details>
                          ) : (
                            <span>{item.excerpt || '-'}</span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div className="card">
                <div style={{ fontWeight: 700, marginBottom: 8 }}>变更</div>
                {changeRows.length === 0 ? (
                  <EmptyState text="暂无字段变更记录" />
                ) : (
                  <div className="grid">
                    {changeRows.map((row, idx) => (
                      <div key={`${row.field}-${idx}`} className="columns-2" style={{ gap: 8 }}>
                        <div><span className="muted">字段：</span>{row.field}</div>
                        <div><span className="muted">时间：</span>{row.observed_at}</div>
                        <div><span className="muted">旧值：</span>{row.old_value}</div>
                        <div><span className="muted">新值：</span>{row.new_value}</div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>关联注册证</CardTitle>
          <CardDescription>注册证是该产品的第一入口（版本链/时间切片/信号）。</CardDescription>
        </CardHeader>
        <CardContent className="grid">
          {anchorRegNo ? (
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
              <Badge variant="muted">registration_no: {anchorRegNo}</Badge>
              <Link className="ui-btn ui-btn--default" href={`/registrations/${encodeURIComponent(anchorRegNo)}`}>
                查看注册证版本链
              </Link>
            </div>
          ) : (
            <EmptyState text="该产品尚未绑定注册证（可在 Admin 做映射）" />
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{res.data.name}</CardTitle>
          <CardDescription>
            {res.data.company ? (
              <>
                <span className="muted">企业：</span>
                <Link href={`/companies/${res.data.company.id}`}>{res.data.company.name}</Link>
              </>
            ) : (
              <span className="muted">企业：-</span>
            )}
          </CardDescription>
        </CardHeader>
        <CardContent className="grid">
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
            <Badge variant="muted">注册证号: {anchorRegNo || '-'}</Badge>
            <Badge variant="muted">UDI-DI: {res.data.udi_di || '-'}</Badge>
            <Badge variant="success">IVD分类: {labelFrom(IVD_CATEGORY_ZH, res.data.ivd_category)}</Badge>
            {res.data.is_stub && res.data.source_hint === 'UDI' && res.data.verified_by_nmpa === false ? (
              <Badge variant="warning">UDI来源｜待NMPA核验</Badge>
            ) : null}
            <Badge
              variant={
                res.data.status === 'active'
                  ? 'success'
                  : res.data.status === 'expired'
                    ? 'warning'
                    : res.data.status === 'cancelled'
                      ? 'danger'
                    : 'muted'
              }
            >
              状态: {labelFrom(STATUS_ZH, res.data.status)}
            </Badge>
          </div>
          <div className="columns-2">
            <div>
              <div className="muted">批准日期</div>
              <div>{res.data.approved_date || '-'}</div>
            </div>
            <div>
              <div className="muted">失效日期</div>
              <div>{res.data.expiry_date || '-'}</div>
            </div>
          </div>
          <div>
            <div className="muted">分类码</div>
            <div>{res.data.class_name || '-'}</div>
          </div>
          <div className="columns-2">
            <div>
              <div className="muted">型号</div>
              <div>{res.data.model || '-'}</div>
            </div>
            <div>
              <div className="muted">规格</div>
              <div>{res.data.specification || '-'}</div>
            </div>
          </div>
          <div>
            <div className="muted">类别</div>
            <div>{res.data.category || '-'}</div>
          </div>
          {res.data.description ? (
            <div>
              <div className="muted">产品描述</div>
              <div style={{ whiteSpace: 'pre-wrap' }}>{res.data.description}</div>
            </div>
          ) : null}
        </CardContent>
      </Card>

      {!isPro ? (
        <ProUpgradeHint
          text={PRO_COPY.product_free_hint}
          ctaHref={PRO_TRIAL_HREF}
        />
      ) : null}

      <LriCard score={lriRes.data?.score || null} isPro={isPro} loadingError={lriRes.error} />

      <Card>
        <CardHeader>
          <CardTitle>包装层级</CardTitle>
          <CardDescription>
            来自 UDI packingList；支持折叠树形查看（一个注册证可对应多个 DI）。
          </CardDescription>
        </CardHeader>
        <CardContent className="grid">
          {!isPro ? (
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
              <span className="muted">专业版解锁：</span>
              <Badge variant="muted">报价对齐</Badge>
              <Badge variant="muted">集采映射</Badge>
              <Badge variant="muted">异常提示</Badge>
              <Badge variant="muted">变更订阅</Badge>
              <Link className="ui-btn ui-btn--default ui-btn--sm" href={PRO_TRIAL_HREF} style={{ marginLeft: 'auto' }}>
                解锁
              </Link>
            </div>
          ) : null}
          {regRes.error ? (
            <ErrorState text={`包装层级加载失败：${regRes.error}`} />
          ) : !regRes.data || (regRes.data.variants || []).length === 0 ? (
            <EmptyState text="暂无包装层级数据（可先运行 udi:variants 生成绑定）。" />
          ) : (
            (regRes.data.variants || []).slice(0, 50).map((v) => {
              const packings = packingsFromPackagingJson(v.packaging_json);
              return (
                <details key={v.di} className="card" open={false}>
                  <summary style={{ cursor: 'pointer', display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                    <Badge variant="muted">DI: {v.di}</Badge>
                    {v.model_spec ? <Badge variant="muted">型号/货号: {v.model_spec}</Badge> : null}
                    {v.manufacturer ? <Badge variant="muted">注册人: {v.manufacturer}</Badge> : null}
                    {packings.length ? <Badge variant="muted">层级: {packings.length}</Badge> : <Badge variant="muted">无层级</Badge>}
                  </summary>
                  <div style={{ marginTop: 10 }}>
                    <PackagingTree packings={packings} />
                  </div>
                </details>
              );
            })
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>储存条件</CardTitle>
          <CardDescription>来自 UDI / 说明书抽取（温度范围、特殊储存条件、标签信息与证据链为专业版能力）。</CardDescription>
        </CardHeader>
        <CardContent className="grid">
          {!isPro ? (
            <ProUpgradeHint
              text="储存条件与标签关键信息属于专业版能力，可用于冷链合规核验与渠道/院内落地。"
              highlights={['温度范围', '特殊储存', '批号/效期', '证据链追溯']}
              ctaHref={PRO_TRIAL_HREF}
            />
          ) : paramsRes.error && paramsRes.status === 401 ? (
            <ErrorState text="当前未登录，登录后可查看储存条件。" />
          ) : paramsRes.error && paramsRes.status === 403 ? (
            <ProUpgradeHint text="当前账号权限不足，升级专业版后可查看储存条件。" ctaHref={PRO_TRIAL_HREF} />
          ) : paramsRes.error ? (
            <ErrorState text={`储存条件加载失败：${paramsRes.error}`} />
          ) : !paramsRes.data ? (
            <EmptyState text="暂无储存条件" />
          ) : (() => {
              const storage = (paramsRes.data.items || []).find((x) => x.param_code === 'STORAGE') || null;
              const storages = storagesFromStorageParam(storage);
              if (!storage) return <EmptyState text="暂无储存条件（STORAGE）" />;
              if (!storages.length) return <div>温度范围: {storage.value_text || '-'}</div>;
              return (
                <div className="grid">
                  <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
                    <Badge variant="muted">温度范围: {storage.value_text || '-'}</Badge>
                    <Badge variant="muted">置信度: {Number(storage.confidence || 0).toFixed(2)}</Badge>
                  </div>
                  <div className="table">
                    <div className="row header">
                      <div>类型</div>
                      <div>范围</div>
                      <div>单位</div>
                    </div>
                    {storages.slice(0, 50).map((s, idx) => (
                      <div className="row" key={idx}>
                        <div>{s?.type || '-'}</div>
                        <div>{s?.range || (s?.min != null && s?.max != null ? `${s.min}~${s.max}${s.unit || ''}` : '-')}</div>
                        <div>{s?.unit || '-'}</div>
                      </div>
                    ))}
                  </div>
                </div>
              );
            })()}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>参数摘要</CardTitle>
          <CardDescription>来源于说明书/附件抽取，包含证据文本。</CardDescription>
        </CardHeader>
        <CardContent className="grid">
          {!isPro ? (
            <ProUpgradeHint
              text="参数与证据链属于专业版能力，用于把监管信息落到可执行的运营与风控动作。"
              highlights={['储存条件', '灭菌方式', '标签信息', '证据链审计']}
              ctaHref={PRO_TRIAL_HREF}
            />
          ) : paramsRes.error && paramsRes.status === 401 ? (
            <ErrorState text="当前未登录，登录后可查看参数与证据链。" />
          ) : paramsRes.error && paramsRes.status === 403 ? (
            <ProUpgradeHint text="当前账号权限不足，升级专业版后可查看参数与证据链。" ctaHref={PRO_TRIAL_HREF} />
          ) : paramsRes.error ? (
            <ErrorState text={`参数加载失败：${paramsRes.error}`} />
          ) : !paramsRes.data || (paramsRes.data.items || []).length === 0 ? (
            <EmptyState text="暂无结构化参数" />
          ) : (
            (paramsRes.data.items || []).slice(0, 20).map((it) => (
              <div key={it.id} className="card">
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
                  <Badge variant="muted">{it.param_code}</Badge>
                  <Badge variant="muted">置信度: {Number(it.confidence || 0).toFixed(2)}</Badge>
                  {it.source ? <Badge variant="muted">来源: {it.source}</Badge> : null}
                </div>
                <div style={{ marginTop: 8 }}>
                  值: {it.value_num ?? it.value_text ?? '-'} {it.unit || ''}
                </div>
                <div className="muted" style={{ marginTop: 6 }}>
                  证据{it.evidence_page != null ? ` (p.${it.evidence_page})` : ''}: {it.evidence_text}
                </div>
              </div>
            ))
          )}
        </CardContent>
      </Card>

      <Card>
        <CardContent>
          <Link href={`/search?reg_no=${encodeURIComponent(res.data.reg_no || '')}`}>按注册证号搜索</Link>
          {res.data.reg_no ? (
            <>
              {' '}
              · <Link href={`/registrations/${encodeURIComponent(res.data.reg_no)}`}>打开注册证详情</Link>
            </>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}
