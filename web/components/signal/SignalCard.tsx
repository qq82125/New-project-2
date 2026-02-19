import Link from 'next/link';

import type { SignalResponse } from '../../lib/api/types';

type SignalCardProps = {
  title?: string;
  signal: SignalResponse;
};

export default function SignalCard({ title = 'Signal', signal }: SignalCardProps) {
  return (
    <section className="rounded border p-4">
      <header className="mb-3">
        <h3 className="text-base font-semibold">{title}</h3>
        <p className="text-sm">Level: {signal.level}</p>
        <p className="text-sm">Score: {signal.score}</p>
        <p className="text-xs text-gray-600">Updated: {signal.updated_at}</p>
      </header>

      <ul className="space-y-2">
        {signal.factors.map((factor) => (
          <li key={factor.name} className="rounded border p-2">
            <p className="text-sm font-medium">
              {factor.name}: {factor.value}
              {factor.unit ? ` ${factor.unit}` : ''}
            </p>
            <p className="text-sm text-gray-700">{factor.explanation}</p>
            {factor.drill_link ? (
              <p className="mt-1 text-sm">
                <Link className="text-blue-700 underline" href={factor.drill_link}>
                  查看依据
                </Link>
              </p>
            ) : null}
          </li>
        ))}
      </ul>
    </section>
  );
}
