import type { RegistrationSummary, RegistrationVariant } from '../../lib/api/registrations';
import type { FieldGroupDictionary } from './FieldGroups';

export type ProductFieldSource = {
  id: string;
  name: string;
  reg_no?: string | null;
  udi_di?: string | null;
  status?: string | null;
  approved_date?: string | null;
  expiry_date?: string | null;
  class_name?: string | null;
  model?: string | null;
  specification?: string | null;
  category?: string | null;
  description?: string | null;
  ivd_category?: string | null;
  company?: { id: string; name: string; country?: string | null } | null;
};

type GroupConfig<T> = {
  id: string;
  title: string;
  fields: Array<{
    key: string;
    label: string;
    getValue: (data: T) => unknown;
  }>;
};

function buildFieldGroups<T>(configs: Array<GroupConfig<T>>, data: T): FieldGroupDictionary[] {
  return configs.map((group) => ({
    id: group.id,
    title: group.title,
    fields: group.fields.map((field) => ({
      key: field.key,
      label: field.label,
      value: field.getValue(data),
    })),
  }));
}

const registrationOverviewConfig: Array<GroupConfig<{ registration: RegistrationSummary; variants: RegistrationVariant[] }>> = [
  {
    id: 'basic',
    title: '基本信息',
    fields: [
      { key: 'registration_no', label: '注册证号', getValue: (d) => d.registration.registration_no },
      { key: 'company', label: '企业名', getValue: (d) => d.registration.company },
      { key: 'status', label: '状态', getValue: (d) => d.registration.status },
      { key: 'filing_no', label: '备案号', getValue: (d) => d.registration.filing_no },
      { key: 'approval_date', label: '批准日期', getValue: (d) => d.registration.approval_date },
      { key: 'expiry_date', label: '失效日期', getValue: (d) => d.registration.expiry_date },
    ],
  },
  {
    id: 'market',
    title: '适用范围',
    fields: [
      { key: 'track', label: '赛道', getValue: (d) => d.registration.track },
      {
        key: 'is_domestic',
        label: '境内',
        getValue: (d) => (d.registration.is_domestic == null ? '' : d.registration.is_domestic ? '是' : '否'),
      },
      { key: 'di_count', label: 'DI数量', getValue: (d) => d.registration.di_count ?? d.variants.length },
    ],
  },
  {
    id: 'structure',
    title: '结构组成',
    fields: [
      { key: 'di_list', label: 'DI列表', getValue: (d) => d.variants.map((x) => x.di).join(' / ') },
      { key: 'first_model_spec', label: '首个型号/货号', getValue: (d) => d.variants[0]?.model_spec },
      { key: 'first_manufacturer', label: '首个注册人', getValue: (d) => d.variants[0]?.manufacturer },
    ],
  },
];

const productOverviewConfig: Array<GroupConfig<{ product: ProductFieldSource; registrationNo: string; diList: string[] }>> = [
  {
    id: 'basic',
    title: '基本信息',
    fields: [
      { key: 'name', label: '产品名', getValue: (d) => d.product.name },
      { key: 'company', label: '企业名', getValue: (d) => d.product.company?.name },
      { key: 'registration_no', label: '注册证号', getValue: (d) => d.registrationNo },
      { key: 'status', label: '状态', getValue: (d) => d.product.status },
      { key: 'approval_date', label: '批准日期', getValue: (d) => d.product.approved_date },
      { key: 'expiry_date', label: '失效日期', getValue: (d) => d.product.expiry_date },
    ],
  },
  {
    id: 'classification',
    title: '分类信息',
    fields: [
      { key: 'ivd_category', label: 'IVD分类', getValue: (d) => d.product.ivd_category },
      { key: 'class_name', label: '分类码', getValue: (d) => d.product.class_name },
      { key: 'category', label: '类别', getValue: (d) => d.product.category },
      { key: 'description', label: '产品描述', getValue: (d) => d.product.description },
    ],
  },
  {
    id: 'structure',
    title: '结构组成',
    fields: [
      { key: 'udi_di', label: 'UDI-DI', getValue: (d) => d.product.udi_di },
      { key: 'model', label: '型号', getValue: (d) => d.product.model },
      { key: 'specification', label: '规格', getValue: (d) => d.product.specification },
      { key: 'di_list', label: 'DI列表', getValue: (d) => d.diList.join(' / ') },
    ],
  },
];

export function buildRegistrationOverviewGroups(registration: RegistrationSummary, variants: RegistrationVariant[]): FieldGroupDictionary[] {
  return buildFieldGroups(registrationOverviewConfig, { registration, variants });
}

export function buildProductOverviewGroups(product: ProductFieldSource, registrationNo: string, diList: string[]): FieldGroupDictionary[] {
  return buildFieldGroups(productOverviewConfig, { product, registrationNo, diList });
}

const FIELD_GROUP_TITLE_BY_KEY: Record<string, string> = {};
const FIELD_LABEL_BY_KEY: Record<string, string> = {};

for (const group of [...registrationOverviewConfig, ...productOverviewConfig]) {
  for (const field of group.fields) {
    FIELD_GROUP_TITLE_BY_KEY[field.key] = group.title;
    FIELD_LABEL_BY_KEY[field.key] = field.label;
  }
}

function normalizeFieldKey(fieldName: string): string {
  const raw = String(fieldName || '').trim();
  if (!raw) return '';
  return raw.split('.').at(-1) || raw;
}

export function resolveFieldGroupTitle(fieldName: string): string {
  const key = normalizeFieldKey(fieldName);
  return FIELD_GROUP_TITLE_BY_KEY[key] || '其他';
}

export function resolveFieldLabel(fieldName: string): string {
  const key = normalizeFieldKey(fieldName);
  return FIELD_LABEL_BY_KEY[key] || key || '未知字段';
}
