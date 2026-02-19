export type SignalLevel =
  | 'low'
  | 'medium'
  | 'high'
  | 'blue'
  | 'moderate'
  | 'red'
  | 'weak'
  | 'medium_growth'
  | 'strong';

export type TimeSliceAt = `at=${string}`;
export type TimeSliceWindow = '3m' | '6m' | '12m' | '24m';
export type TimeSliceParams = { at: string } | { window: TimeSliceWindow };

export type SignalIndexKey = 'registration_lifecycle' | 'track_competition' | 'company_growth';

export type SignalFactor = {
  name: string;
  value: string | number;
  unit?: string;
  explanation: string;
  drill_link?: string;
};

export type SignalResponse = {
  level: SignalLevel;
  score: number;
  factors: SignalFactor[];
  updated_at: string;
};

export type EvidenceRef = {
  source: string;
  source_url?: string;
  page?: string | number;
  excerpt?: string;
  raw_document_id?: string;
  hash?: string;
  observed_at?: string;
  run_id?: string;
};

export type TimelineEvent = {
  event_id: string;
  event_type: 'create' | 'change' | 'renew' | 'cancel';
  observed_at: string;
  title?: string;
  diff?: unknown;
  diff_summary?: string;
  evidence_refs?: EvidenceRef[];
};
