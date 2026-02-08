'use client';

import { ErrorState } from '../components/States';

export default function Error({ reset }: { reset: () => void }) {
  return (
    <div className="grid">
      <ErrorState text="页面加载失败，请稍后重试" />
      <button onClick={reset}>重试</button>
    </div>
  );
}
