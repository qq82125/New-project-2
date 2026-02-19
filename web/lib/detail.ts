import type { EvidenceRef, TimelineEvent } from './api/types';

export type DetailEvidence = {
  source: string;
  observed_at: string;
  excerpt: string;
};

export type DetailChange = {
  field: string;
  old_value: string;
  new_value: string;
  observed_at: string;
};

function text(v: unknown): string {
  if (v === null || v === undefined) return '-';
  if (typeof v === 'string') return v || '-';
  if (typeof v === 'number' || typeof v === 'boolean') return String(v);
  try {
    return JSON.stringify(v);
  } catch {
    return String(v);
  }
}

export function toEvidenceRows(events: TimelineEvent[]): DetailEvidence[] {
  const out: DetailEvidence[] = [];
  for (const event of events || []) {
    const refs = (event.evidence_refs || []) as EvidenceRef[];
    for (const ref of refs) {
      out.push({
        source: text(ref.source),
        observed_at: text(ref.observed_at || event.observed_at),
        excerpt: text(ref.excerpt || ''),
      });
    }
  }
  return out;
}

function extractFromObject(diff: Record<string, unknown>, observedAt: string): DetailChange[] {
  const rows: DetailChange[] = [];
  for (const [k, v] of Object.entries(diff)) {
    if (v && typeof v === 'object' && !Array.isArray(v)) {
      const rec = v as Record<string, unknown>;
      if ('old' in rec || 'new' in rec || 'before' in rec || 'after' in rec) {
        rows.push({
          field: k,
          old_value: text(rec.old ?? rec.before ?? '-'),
          new_value: text(rec.new ?? rec.after ?? '-'),
          observed_at: observedAt,
        });
        continue;
      }
    }
    rows.push({
      field: k,
      old_value: '-',
      new_value: text(v),
      observed_at: observedAt,
    });
  }
  return rows;
}

export function toChangeRows(events: TimelineEvent[]): DetailChange[] {
  const out: DetailChange[] = [];
  const sorted = [...(events || [])].sort((a, b) => String(b.observed_at || '').localeCompare(String(a.observed_at || '')));
  for (const event of sorted) {
    const observedAt = text(event.observed_at);
    const diff = event.diff;
    if (!diff) continue;

    if (Array.isArray(diff)) {
      for (const item of diff) {
        if (item && typeof item === 'object' && !Array.isArray(item)) {
          const rec = item as Record<string, unknown>;
          out.push({
            field: text(rec.field || rec.name || 'field'),
            old_value: text(rec.old ?? rec.before ?? '-'),
            new_value: text(rec.new ?? rec.after ?? '-'),
            observed_at: observedAt,
          });
        }
      }
      continue;
    }

    if (typeof diff === 'object') {
      out.push(...extractFromObject(diff as Record<string, unknown>, observedAt));
      continue;
    }

    out.push({
      field: 'diff',
      old_value: '-',
      new_value: text(diff),
      observed_at: observedAt,
    });
  }
  return out;
}
