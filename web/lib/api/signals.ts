import { apiGet } from './client';
import { ApiHttpError } from './client';
import type { SignalResponse } from './types';

type ApiEnvelope<T> = {
  code: number;
  message?: string;
  data: T;
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

export async function getRegistrationSignal(no: string): Promise<SignalResponse> {
  const payload = await apiGet<SignalResponse | ApiEnvelope<SignalResponse>>(
    `/api/signals/registration/${encodeURIComponent(no)}`,
  );
  return unwrapEnvelope(payload);
}

export async function getTrackSignal(trackId: string): Promise<SignalResponse> {
  const payload = await apiGet<SignalResponse | ApiEnvelope<SignalResponse>>(
    `/api/signals/track/${encodeURIComponent(trackId)}`,
  );
  return unwrapEnvelope(payload);
}

export async function getCompanySignal(companyId: string): Promise<SignalResponse> {
  const payload = await apiGet<SignalResponse | ApiEnvelope<SignalResponse>>(
    `/api/signals/company/${encodeURIComponent(companyId)}`,
  );
  return unwrapEnvelope(payload);
}

export type TopRiskRegistrationItem = {
  registration_no: string;
  company?: string | null;
  level?: string | null;
  days_to_expiry?: number | null;
};

export type TopCompetitiveTrackItem = {
  track_id: string;
  track_name: string;
  level?: string | null;
  total_count?: number | null;
  new_rate_12m?: number | null;
};

export type TopGrowthCompanyItem = {
  company_id: string;
  company_name: string;
  level?: string | null;
  new_registrations_12m?: number | null;
  new_tracks_12m?: number | null;
};

type TopListEnvelope<T> = { items: T[] };

export async function getTopRiskRegistrations(): Promise<TopListEnvelope<TopRiskRegistrationItem>> {
  const payload = await apiGet<TopListEnvelope<TopRiskRegistrationItem> | ApiEnvelope<TopListEnvelope<TopRiskRegistrationItem>>>(
    '/api/signals/top-risk-registrations',
  );
  const data = unwrapEnvelope(payload);
  return { items: Array.isArray(data.items) ? data.items : [] };
}

export async function getTopCompetitiveTracks(): Promise<TopListEnvelope<TopCompetitiveTrackItem>> {
  const payload = await apiGet<TopListEnvelope<TopCompetitiveTrackItem> | ApiEnvelope<TopListEnvelope<TopCompetitiveTrackItem>>>(
    '/api/signals/top-competitive-tracks',
  );
  const data = unwrapEnvelope(payload);
  return { items: Array.isArray(data.items) ? data.items : [] };
}

export async function getTopGrowthCompanies(): Promise<TopListEnvelope<TopGrowthCompanyItem>> {
  const payload = await apiGet<TopListEnvelope<TopGrowthCompanyItem> | ApiEnvelope<TopListEnvelope<TopGrowthCompanyItem>>>(
    '/api/signals/top-growth-companies',
  );
  const data = unwrapEnvelope(payload);
  return { items: Array.isArray(data.items) ? data.items : [] };
}

export type SearchSignalItem = {
  registration_no: string;
  lifecycle_level?: string | null;
  track_level?: string | null;
  company_level?: string | null;
  factors_summary?: string | null;
};

type SearchSignalBatchResponse = {
  items: SearchSignalItem[];
};

export async function getSearchSignalsBatch(registrationNos: string[]): Promise<SearchSignalBatchResponse> {
  const uniq = Array.from(new Set((registrationNos || []).map((x) => x.trim()).filter(Boolean)));
  if (uniq.length === 0) return { items: [] };

  try {
    const payload = await apiGet<SearchSignalBatchResponse | ApiEnvelope<SearchSignalBatchResponse>>(
      '/api/signals/batch',
      { registration_nos: uniq.join(',') },
    );
    const data = unwrapEnvelope(payload);
    return { items: Array.isArray(data.items) ? data.items : [] };
  } catch (err) {
    // Batch endpoint might not be available yet. Fallback to single calls with bounded concurrency.
    if (!(err instanceof ApiHttpError) || err.status !== 404) throw err;

    const out: SearchSignalItem[] = [];
    const queue = [...uniq];
    const workerCount = Math.min(5, queue.length);

    async function worker() {
      // Keep concurrency <= 5 to avoid overloading the signal API.
      while (queue.length > 0) {
        const regNo = queue.shift();
        if (!regNo) return;
        try {
          const signal = await getRegistrationSignal(regNo);
          out.push({
            registration_no: regNo,
            lifecycle_level: signal.level,
          });
        } catch (singleErr) {
          if (singleErr instanceof ApiHttpError && singleErr.status === 404) continue;
        }
      }
    }

    await Promise.all(Array.from({ length: workerCount }, () => worker()));
    return { items: out };
  }
}
