import type { TimelineEvent } from '../../lib/api/types';
import EvidencePanel from '../evidence/EvidencePanel';
import DiffViewer from './DiffViewer';

type VersionChainTimelineProps = {
  events: TimelineEvent[];
};

export default function VersionChainTimeline({ events }: VersionChainTimelineProps) {
  return (
    <section className="rounded border p-4">
      <h3 className="mb-3 text-base font-semibold">Version Chain</h3>
      {events.length === 0 ? (
        <p className="text-sm text-gray-700">暂无事件</p>
      ) : (
        <ul className="space-y-2">
          {events.map((event) => (
            <li key={event.event_id} className="rounded border p-2">
              <details>
                <summary className="cursor-pointer text-sm font-medium">
                  [{event.event_type}] {event.title || event.event_id} · {event.observed_at}
                </summary>
                <div className="mt-3 space-y-3">
                  <DiffViewer diff={event.diff} diffSummary={event.diff_summary} />
                  <EvidencePanel evidenceRefs={event.evidence_refs} />
                </div>
              </details>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
