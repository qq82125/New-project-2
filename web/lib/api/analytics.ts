import { apiGet } from './client';

type ApiEnvelope<T> = {
  code: number;
  message?: string;
  data: T;
};

export type TimeSliceWindow = '3m' | '6m' | '12m' | '24m';

export type TimeSliceMetrics = {
  stock_count?: number | null;
  new_count?: number | null;
  cancel_count?: number | null;
  renew_count?: number | null;
  items?: unknown[];
};

export type RegistrationListItem = {
  registration_no: string;
  company?: string | null;
  track?: string | null;
  status?: string | null;
  expiry_date?: string | null;
};

export type RegistrationListResponse = {
  items: RegistrationListItem[];
  total: number;
};

type FilterParams = {
  track?: string;
  company?: string;
  category?: string;
  origin?: string;
  status?: string;
};

function unwrapEnvelope<T>(payload: T | ApiEnvelope<T>): T {
  if (
    payload &&
    typeof payload === 'object' &&
    'code' in payload &&
    typeof (payload as { code?: unknown }).code === 'number' &&
    'data' in payload
  ) {
    const wrapped = payload as ApiEnvelope<T>;
    if (wrapped.code !== 0) {
      throw new Error(wrapped.message || `API returned non-zero code: ${wrapped.code}`);
    }
    return wrapped.data;
  }
  return payload as T;
}

function compactParams(params: Record<string, string | undefined>): Record<string, string> {
  const out: Record<string, string> = {};
  Object.entries(params).forEach(([k, v]) => {
    if (v === undefined) return;
    const s = String(v).trim();
    if (!s) return;
    out[k] = s;
  });
  return out;
}

export async function getTimeSliceMetrics(
  mode: { at: string } | { window: TimeSliceWindow },
  filters: FilterParams,
): Promise<TimeSliceMetrics> {
  const params = compactParams({
    track: filters.track,
    company: filters.company,
    category: filters.category,
    origin: filters.origin,
    status: filters.status,
    ...(Object.prototype.hasOwnProperty.call(mode, 'at')
      ? { at: (mode as { at: string }).at }
      : { window: (mode as { window: TimeSliceWindow }).window }),
  });
  const payload = await apiGet<TimeSliceMetrics | ApiEnvelope<TimeSliceMetrics>>('/api/analytics/time-slice', params);
  return unwrapEnvelope(payload);
}

export async function getRegistrationsList(
  filters: FilterParams & { page: number; page_size: number },
): Promise<RegistrationListResponse> {
  const params = compactParams({
    track: filters.track,
    company: filters.company,
    category: filters.category,
    origin: filters.origin,
    status: filters.status,
    page: String(filters.page),
    page_size: String(filters.page_size),
  });
  const payload = await apiGet<RegistrationListResponse | ApiEnvelope<RegistrationListResponse>>(
    '/api/registrations/list',
    params,
  );
  const data = unwrapEnvelope(payload);
  return {
    items: Array.isArray(data.items) ? data.items : [],
    total: Number(data.total || 0),
  };
}
