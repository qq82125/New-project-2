import { apiGet } from './client';
import type { RegistrationDiffList, TimelineEvent } from './types';

type ApiEnvelope<T> = {
  code: number;
  message?: string;
  data: T;
};

export type RegistrationVariant = {
  di: string;
  model_spec?: string | null;
  manufacturer?: string | null;
  packaging_json?: unknown[] | unknown | null;
  evidence_raw_document_id?: string | null;
};

export type RegistrationSummary = {
  registration_no: string;
  company?: string | null;
  track?: string | null;
  status?: string | null;
  expiry_date?: string | null;
  is_domestic?: boolean | null;
  di_count?: number | null;
  filing_no?: string | null;
  approval_date?: string | null;
  is_stub?: boolean | null;
  source_hint?: string | null;
  verified_by_nmpa?: boolean | null;
  variants?: RegistrationVariant[];
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

export async function getRegistration(no: string): Promise<RegistrationSummary> {
  const payload = await apiGet<RegistrationSummary | ApiEnvelope<RegistrationSummary>>(
    `/api/registrations/${encodeURIComponent(no)}`,
  );
  return unwrapEnvelope(payload);
}

export async function getRegistrationTimeline(no: string): Promise<TimelineEvent[]> {
  const payload = await apiGet<TimelineEvent[] | ApiEnvelope<TimelineEvent[]>>(
    `/api/registrations/${encodeURIComponent(no)}/timeline`,
  );
  const data = unwrapEnvelope(payload);
  return Array.isArray(data) ? data : [];
}

export async function getRegistrationSnapshot(no: string, at: string): Promise<unknown> {
  const payload = await apiGet<unknown | ApiEnvelope<unknown>>(
    `/api/registrations/${encodeURIComponent(no)}/snapshot`,
    { at },
  );
  return unwrapEnvelope(payload);
}

export async function getRegistrationDiffs(no: string, limit = 5, offset = 0): Promise<RegistrationDiffList> {
  const payload = await apiGet<RegistrationDiffList | ApiEnvelope<RegistrationDiffList>>(
    `/api/registrations/${encodeURIComponent(no)}/diffs`,
    { limit: String(limit), offset: String(offset) },
  );
  const data = unwrapEnvelope(payload);
  return {
    items: Array.isArray(data?.items) ? data.items : [],
    total: Number(data?.total || 0),
  };
}
