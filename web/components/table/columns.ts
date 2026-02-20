import type { UnifiedBadgeToken } from '../common/UnifiedBadge';

export type UnifiedColumnKey =
  | 'product_name'
  | 'company_name'
  | 'registration_no'
  | 'status'
  | 'expiry_date'
  | 'udi_di'
  | 'change_count_30d'
  | 'di_count'
  | 'params_coverage'
  | 'risk_level'
  | 'badges'
  | 'actions';

export type UnifiedTableRow = {
  id: string;
  product_name: string;
  company_name: string;
  registration_no: string;
  status: string;
  expiry_date: string;
  udi_di: string;
  change_count_30d?: number | null;
  di_count?: number | null;
  params_coverage?: number | null;
  risk_level?: string | null;
  badges: UnifiedBadgeToken[];
  detail_href: string;
  action?: {
    label?: string;
    href?: string;
    disabled?: boolean;
    type?: 'link' | 'benchmark';
    registration_no?: string;
    set_id?: string;
  };
};

export const DEFAULT_UNIFIED_COLUMNS: UnifiedColumnKey[] = [
  'product_name',
  'company_name',
  'registration_no',
  'status',
  'expiry_date',
  'udi_di',
  'badges',
];

export const BENCHMARK_COLUMNS: UnifiedColumnKey[] = [
  'product_name',
  'company_name',
  'registration_no',
  'status',
  'expiry_date',
  'di_count',
  'change_count_30d',
  'params_coverage',
  'risk_level',
  'actions',
];

export const UNIFIED_COLUMN_LABELS: Record<UnifiedColumnKey, string> = {
  product_name: '产品名',
  company_name: '企业名',
  registration_no: '注册证号',
  status: '状态',
  expiry_date: '失效日期',
  udi_di: 'UDI-DI',
  change_count_30d: '30天变更',
  di_count: 'DI数量',
  params_coverage: '参数覆盖',
  risk_level: '风险等级',
  badges: 'badges',
  actions: '操作',
};
