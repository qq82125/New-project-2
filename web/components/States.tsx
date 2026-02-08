export function LoadingState({ text = '加载中...' }: { text?: string }) {
  return <div className="card muted">{text}</div>;
}

export function EmptyState({ text = '暂无数据' }: { text?: string }) {
  return <div className="card muted">{text}</div>;
}

export function ErrorState({ text = '加载失败' }: { text?: string }) {
  return <div className="card error">{text}</div>;
}
