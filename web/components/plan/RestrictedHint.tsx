import { PRO_COPY } from '../../constants/pro';

export default function RestrictedHint({ text }: { text?: string }) {
  return (
    <div
      className="muted"
      style={{
        marginTop: 10,
        paddingTop: 10,
        borderTop: '1px solid rgba(207, 224, 213, 0.7)',
        fontSize: 13,
      }}
    >
      {text || PRO_COPY.restricted_hint}
    </div>
  );
}
