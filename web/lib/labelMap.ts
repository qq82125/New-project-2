// Centralized UI label mapping (Chinese display only).
// Do NOT change API field names/values; this is presentation-only.

export const FIELD_LABELS: Record<string, string> = {
  // Product
  name: '产品名称',
  reg_no: '注册证号',
  udi_di: 'UDI-DI',
  status: '状态',
  approved_date: '批准日期',
  expiry_date: '有效期至',
  class_name: '类别',
  company: '企业',

  // Runs / Status
  started_at: '开始时间',
  finished_at: '结束时间',
  message: '消息',
  records: '记录',
  added_updated_removed: '新增/更新/移除',
};

export const STATUS_LABELS: Record<string, string> = {
  active: '有效',
  cancelled: '已注销',
  expired: '已过期',
};

export const RUN_STATUS_LABELS: Record<string, string> = {
  success: '成功',
  failed: '失败',
  running: '运行中',
};

export const SORT_BY_LABELS: Record<string, string> = {
  updated_at: '更新时间',
  approved_date: '批准日期',
  expiry_date: '有效期',
  name: '产品名称',
};

export const SORT_ORDER_LABELS: Record<string, string> = {
  desc: '降序',
  asc: '升序',
};

export const RUN_SOURCE_LABELS: Record<string, string> = {
  nmpa_registry: 'NMPA 注册证',
  nmpa_udi: 'NMPA UDI',
  nmpa_supplement: 'NMPA 补充源',
  nhsa: '国家医保编码（NHSA）',
  procurement: '招采',
  local_registry: '本地注册库',
};

export function labelField(key: string, fallback?: string) {
  return FIELD_LABELS[key] || fallback || key;
}

export function labelStatus(value?: string | null) {
  const v = String(value || '').toLowerCase();
  return STATUS_LABELS[v] || (value || '-');
}

export function labelRunStatus(value?: string | null) {
  const v = String(value || '').toLowerCase();
  return RUN_STATUS_LABELS[v] || (value || '-');
}

export function labelSortBy(value?: string | null) {
  const v = String(value || '').toLowerCase();
  return SORT_BY_LABELS[v] || (value || '-');
}

export function labelSortOrder(value?: string | null) {
  const v = String(value || '').toLowerCase();
  return SORT_ORDER_LABELS[v] || (value || '-');
}

export function labelRunSource(value?: string | null) {
  const v = String(value || '').toLowerCase();
  return RUN_SOURCE_LABELS[v] || (value || '-');
}

export function formatUdiDiDisplay(value?: string | null) {
  const raw = String(value || '').trim();
  if (!raw) return '-';
  const m = raw.match(/^reg:\s*(.+)$/i);
  if (m && m[1]) {
    return `（未提供，使用注册证号关联）${m[1]}`;
  }
  return raw;
}
