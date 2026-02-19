import type { UnifiedBadgeToken } from '../common/UnifiedBadge';

export type UnifiedColumnKey =
  | 'product_name'
  | 'company_name'
  | 'registration_no'
  | 'status'
  | 'expiry_date'
  | 'udi_di'
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

export const UNIFIED_COLUMN_LABELS: Record<UnifiedColumnKey, string> = {
  product_name: '产品名',
  company_name: '企业名',
  registration_no: '注册证号',
  status: '状态',
  expiry_date: '失效日期',
  udi_di: 'UDI-DI',
  badges: 'badges',
  actions: '操作',
};
