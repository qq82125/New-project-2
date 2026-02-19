import { apiGet } from './client';

type ApiEnvelope<T> = {
  code: number;
  message?: string;
  data: T;
};

export type CompanySummary = {
  company_id: string;
  company_name: string;
  origin?: string | null;
  current_registrations?: number | null;
  current_tracks?: number | null;
};

export type CompanyTrajectoryPoint = {
  month: string;
  total: number;
  new_count: number;
  cancel_count: number;
  net_change: number;
};

export type CompanyTrajectory = {
  series: CompanyTrajectoryPoint[];
};

export type CompanyNewTrack = {
  month: string;
  track_id: string;
  track_name: string;
};

export type CompanyNewTracks = {
  items: CompanyNewTrack[];
};

export type CompanyHighRiskRegistration = {
  registration_no: string;
  company?: string | null;
  expiry_date?: string | null;
  level?: string | null;
};

export type CompanyHighRiskRegistrations = {
  items: CompanyHighRiskRegistration[];
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

export async function getCompany(companyId: string): Promise<CompanySummary> {
  const payload = await apiGet<CompanySummary | ApiEnvelope<CompanySummary>>(
    `/api/companies/${encodeURIComponent(companyId)}`,
  );
  return unwrapEnvelope(payload);
}

export async function getCompanyTrajectory(companyId: string, window: '24m' = '24m'): Promise<CompanyTrajectory> {
  const payload = await apiGet<CompanyTrajectory | ApiEnvelope<CompanyTrajectory>>(
    `/api/companies/${encodeURIComponent(companyId)}/trajectory`,
    { window },
  );
  const data = unwrapEnvelope(payload);
  return { series: Array.isArray(data.series) ? data.series : [] };
}

export async function getCompanyNewTracks(companyId: string, window: '24m' = '24m'): Promise<CompanyNewTracks> {
  const payload = await apiGet<CompanyNewTracks | ApiEnvelope<CompanyNewTracks>>(
    `/api/companies/${encodeURIComponent(companyId)}/new-tracks`,
    { window },
  );
  const data = unwrapEnvelope(payload);
  return { items: Array.isArray(data.items) ? data.items : [] };
}

export async function getCompanyHighRiskRegistrations(
  companyId: string,
  window: '12m' = '12m',
): Promise<CompanyHighRiskRegistrations> {
  const payload = await apiGet<CompanyHighRiskRegistrations | ApiEnvelope<CompanyHighRiskRegistrations>>(
    `/api/companies/${encodeURIComponent(companyId)}/high-risk-registrations`,
    { window },
  );
  const data = unwrapEnvelope(payload);
  return { items: Array.isArray(data.items) ? data.items : [] };
}
