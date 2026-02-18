export const STATUS_ZH: Record<string, string> = {
  active: '有效',
  cancelled: '已注销',
  expired: '已过期',
};

export const SORT_BY_ZH: Record<string, string> = {
  updated_at: '最近更新',
  approved_date: '批准日期',
  expiry_date: '失效日期',
  name: '产品名称',
};

export const SORT_ORDER_ZH: Record<string, string> = {
  asc: '升序',
  desc: '降序',
};

export const IVD_CATEGORY_ZH: Record<string, string> = {
  reagent: '试剂',
  instrument: '仪器',
  software: '软件',
};

export const CHANGE_TYPE_ZH: Record<string, string> = {
  new: '新增',
  update: '变更',
  expire: '失效',
  cancel: '注销',
  created: '新增',
  updated: '变更',
  removed: '移除',
  status_changed: '状态变化',
};

export const FIELD_ZH: Record<string, string> = {
  reg_no: '注册证号',
  udi_di: 'UDI-DI',
  change_type: '变化类型',
  ivd_category: 'IVD分类',
};

export const PLAN_ZH: Record<string, string> = {
  free: '免费版',
  pro: '专业版',
  pro_annual: '专业版（年度）',
};

export const PLAN_STATUS_ZH: Record<string, string> = {
  active: '有效',
  trial: '试用中',
  inactive: '未生效',
  suspended: '已暂停',
  expired: '已过期',
  revoked: '已撤销',
  cancelled: '已注销',
};

export const ROLE_ZH: Record<string, string> = {
  admin: '管理员',
  user: '普通用户',
};

export const RUN_STATUS_ZH: Record<string, string> = {
  queued: '排队中',
  running: '执行中',
  success: '成功',
  failed: '失败',
  cancelled: '已取消',
};

export const SOURCE_TYPE_ZH: Record<string, string> = {
  postgres: 'PostgreSQL',
  local_registry: '本地注册库目录',
};

export const LRI_RISK_ZH: Record<string, string> = {
  LOW: '低风险',
  MID: '中风险',
  HIGH: '高风险',
  CRITICAL: '极高风险',
};

export function labelFrom(map: Record<string, string>, value?: string | null): string {
  if (!value) return '-';
  return map[value] || value;
}
