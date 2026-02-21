import { EmptyState } from '../States';

type DictionaryField = {
  key: string;
  label: string;
  value: unknown;
};

export type FieldGroupDictionary = {
  id: string;
  title: string;
  fields: DictionaryField[];
};

function isEmptyValue(value: unknown): boolean {
  if (value === null || value === undefined) return true;
  if (typeof value === 'string') return value.trim() === '' || value.trim() === '-';
  if (Array.isArray(value)) return value.length === 0;
  return false;
}

function viewText(value: unknown): string {
  if (typeof value === 'string') return value;
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  if (Array.isArray(value)) return value.join(' / ');
  if (value && typeof value === 'object') {
    try {
      return JSON.stringify(value);
    } catch {
      return String(value);
    }
  }
  return '';
}

function FieldRow({ label, value }: { label: string; value: unknown }) {
  const text = viewText(value);
  const isLong = text.length > 120;
  return (
    <div className="columns-2" style={{ gap: 8 }}>
      <div className="muted">{label}</div>
      <div>
        {isLong ? (
          <details>
            <summary>show more</summary>
            <div style={{ marginTop: 6, whiteSpace: 'pre-wrap' }}>{text}</div>
          </details>
        ) : (
          <span>{text}</span>
        )}
      </div>
    </div>
  );
}

export default function FieldGroups({ groups, emptyText = '暂无可展示字段' }: { groups: FieldGroupDictionary[]; emptyText?: string }) {
  const filtered = groups
    .map((group) => ({
      ...group,
      fields: group.fields.filter((field) => !isEmptyValue(field.value)),
    }))
    .filter((group) => group.fields.length > 0);

  if (filtered.length === 0) {
    return <EmptyState text={emptyText} />;
  }

  return (
    <div className="grid">
      {filtered.map((group) => (
        <details key={group.id} className="card" open>
          <summary style={{ cursor: 'pointer', fontWeight: 700 }}>{group.title}</summary>
          <div className="grid" style={{ marginTop: 10 }}>
            {group.fields.map((field) => (
              <FieldRow key={`${group.id}:${field.key}`} label={field.label} value={field.value} />
            ))}
          </div>
        </details>
      ))}
    </div>
  );
}
