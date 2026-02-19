type DiffViewerProps = {
  diff?: unknown;
  diffSummary?: string;
};

export default function DiffViewer({ diff, diffSummary }: DiffViewerProps) {
  if (!diff) {
    return (
      <section className="rounded border p-3">
        <h4 className="mb-2 text-sm font-semibold">Diff</h4>
        <p className="text-sm text-gray-700">本次事件无结构化字段差异</p>
        {diffSummary ? <p className="mt-2 text-xs text-gray-600">{diffSummary}</p> : null}
      </section>
    );
  }

  return (
    <section className="rounded border p-3">
      <h4 className="mb-2 text-sm font-semibold">Diff</h4>
      {diffSummary ? <p className="mb-2 text-sm text-gray-700">{diffSummary}</p> : null}
      <pre className="overflow-auto rounded bg-gray-50 p-2 text-xs">{JSON.stringify(diff, null, 2)}</pre>
    </section>
  );
}
