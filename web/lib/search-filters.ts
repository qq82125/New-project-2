export type SearchChangeType = 'new' | 'update' | 'cancel';
export type SearchDateRange = '7d' | '30d' | '90d' | '12m';
export type SearchRisk = 'high' | 'medium' | 'low';
export type SearchSort = 'recency' | 'risk' | 'lri' | 'competition';
export type SearchView = 'table' | 'compact';

export type SearchFilters = {
  q: string;
  track: string;
  company: string;
  country_or_region: string;
  status: string;
  change_type: SearchChangeType | '';
  date_range: SearchDateRange | '';
  risk: SearchRisk | '';
  sort: SearchSort;
  view: SearchView;
};

type Chip = { key: keyof SearchFilters; label: string; value: string };

const CHANGE_TYPE_SET = new Set<SearchChangeType>(['new', 'update', 'cancel']);
const DATE_RANGE_SET = new Set<SearchDateRange>(['7d', '30d', '90d', '12m']);
const RISK_SET = new Set<SearchRisk>(['high', 'medium', 'low']);
const SORT_SET = new Set<SearchSort>(['recency', 'risk', 'lri', 'competition']);
const VIEW_SET = new Set<SearchView>(['table', 'compact']);

export const SEARCH_FILTER_DEFAULTS: SearchFilters = {
  q: '',
  track: '',
  company: '',
  country_or_region: '',
  status: '',
  change_type: '',
  date_range: '',
  risk: '',
  sort: 'recency',
  view: 'table',
};

function cleanText(v: string | null | undefined): string {
  return String(v || '').trim();
}

export function parseSearchUrl(params: URLSearchParams): SearchFilters {
  const q = cleanText(params.get('q'));
  const track = cleanText(params.get('track'));
  const company = cleanText(params.get('company'));
  const country_or_region = cleanText(params.get('country_or_region'));
  const status = cleanText(params.get('status'));

  const changeTypeRaw = cleanText(params.get('change_type'));
  const dateRangeRaw = cleanText(params.get('date_range'));
  const riskRaw = cleanText(params.get('risk'));
  const sortRaw = cleanText(params.get('sort'));
  const viewRaw = cleanText(params.get('view'));

  return {
    q,
    track,
    company,
    country_or_region,
    status,
    change_type: CHANGE_TYPE_SET.has(changeTypeRaw as SearchChangeType) ? (changeTypeRaw as SearchChangeType) : '',
    date_range: DATE_RANGE_SET.has(dateRangeRaw as SearchDateRange) ? (dateRangeRaw as SearchDateRange) : '',
    risk: RISK_SET.has(riskRaw as SearchRisk) ? (riskRaw as SearchRisk) : '',
    sort: SORT_SET.has(sortRaw as SearchSort) ? (sortRaw as SearchSort) : SEARCH_FILTER_DEFAULTS.sort,
    view: VIEW_SET.has(viewRaw as SearchView) ? (viewRaw as SearchView) : SEARCH_FILTER_DEFAULTS.view,
  };
}

export function buildSearchUrl(filters: Partial<SearchFilters>): string {
  const merged: SearchFilters = {
    ...SEARCH_FILTER_DEFAULTS,
    ...filters,
    q: cleanText(filters.q),
    track: cleanText(filters.track),
    company: cleanText(filters.company),
    country_or_region: cleanText(filters.country_or_region),
    status: cleanText(filters.status),
    change_type: CHANGE_TYPE_SET.has(String(filters.change_type || '') as SearchChangeType)
      ? (filters.change_type as SearchChangeType)
      : '',
    date_range: DATE_RANGE_SET.has(String(filters.date_range || '') as SearchDateRange)
      ? (filters.date_range as SearchDateRange)
      : '',
    risk: RISK_SET.has(String(filters.risk || '') as SearchRisk)
      ? (filters.risk as SearchRisk)
      : '',
    sort: SORT_SET.has(String(filters.sort || '') as SearchSort)
      ? (filters.sort as SearchSort)
      : SEARCH_FILTER_DEFAULTS.sort,
    view: VIEW_SET.has(String(filters.view || '') as SearchView)
      ? (filters.view as SearchView)
      : SEARCH_FILTER_DEFAULTS.view,
  };

  const sp = new URLSearchParams();
  if (merged.q) sp.set('q', merged.q);
  if (merged.track) sp.set('track', merged.track);
  if (merged.company) sp.set('company', merged.company);
  if (merged.country_or_region) sp.set('country_or_region', merged.country_or_region);
  if (merged.status) sp.set('status', merged.status);
  if (merged.change_type) sp.set('change_type', merged.change_type);
  if (merged.date_range) sp.set('date_range', merged.date_range);
  if (merged.risk) sp.set('risk', merged.risk);
  if (merged.sort !== SEARCH_FILTER_DEFAULTS.sort) sp.set('sort', merged.sort);
  if (merged.view !== SEARCH_FILTER_DEFAULTS.view) sp.set('view', merged.view);

  const query = sp.toString();
  return query ? `/search?${query}` : '/search';
}

export function serializeFiltersToChips(filters: SearchFilters): Chip[] {
  const chips: Chip[] = [];
  if (filters.q) chips.push({ key: 'q', label: '关键词', value: filters.q });
  if (filters.track) chips.push({ key: 'track', label: '赛道', value: filters.track });
  if (filters.company) chips.push({ key: 'company', label: '企业', value: filters.company });
  if (filters.country_or_region) chips.push({ key: 'country_or_region', label: '国家/地区', value: filters.country_or_region });
  if (filters.status) chips.push({ key: 'status', label: '状态', value: filters.status });
  if (filters.change_type) chips.push({ key: 'change_type', label: '变更类型', value: filters.change_type });
  if (filters.date_range) chips.push({ key: 'date_range', label: '时间窗', value: filters.date_range });
  if (filters.risk) chips.push({ key: 'risk', label: '风险', value: filters.risk });
  if (filters.sort !== SEARCH_FILTER_DEFAULTS.sort) chips.push({ key: 'sort', label: '排序', value: filters.sort });
  if (filters.view !== SEARCH_FILTER_DEFAULTS.view) chips.push({ key: 'view', label: '视图', value: filters.view });
  return chips;
}
