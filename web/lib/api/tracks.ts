import { apiGet } from './client';

type ApiEnvelope<T> = {
  code: number;
  message?: string;
  data: T;
};

export type TrackInfo = {
  track_id: string;
  track_name: string;
  description?: string | null;
};

export type TrackStatsPoint = {
  month: string;
  new_count: number;
};

export type TrackStats = {
  series: TrackStatsPoint[];
};

export type TrackRegistrationItem = {
  registration_no: string;
  company?: string | null;
  status?: string | null;
  expiry_date?: string | null;
};

export type TrackRegistrations = {
  items: TrackRegistrationItem[];
  total: number;
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

export async function getTrack(trackId: string): Promise<TrackInfo> {
  const payload = await apiGet<TrackInfo | ApiEnvelope<TrackInfo>>(`/api/tracks/${encodeURIComponent(trackId)}`);
  return unwrapEnvelope(payload);
}

export async function getTrackStats(trackId: string, window: '12m' = '12m'): Promise<TrackStats> {
  const payload = await apiGet<TrackStats | ApiEnvelope<TrackStats>>(
    `/api/tracks/${encodeURIComponent(trackId)}/stats`,
    { window },
  );
  const data = unwrapEnvelope(payload);
  return {
    series: Array.isArray(data.series) ? data.series : [],
  };
}

export async function getTrackRegistrations(
  trackId: string,
  page: number,
  pageSize: number,
): Promise<TrackRegistrations> {
  const payload = await apiGet<TrackRegistrations | ApiEnvelope<TrackRegistrations>>(
    `/api/tracks/${encodeURIComponent(trackId)}/registrations`,
    { page: String(page), page_size: String(pageSize) },
  );
  const data = unwrapEnvelope(payload);
  return {
    items: Array.isArray(data.items) ? data.items : [],
    total: Number(data.total || 0),
  };
}
