import { ReactNode } from 'react';
import { Card, CardContent } from './card';

function Icon({ children }: { children: ReactNode }) {
  return <div className="ui-feedback__icon">{children}</div>;
}

function Feedback({
  title,
  text,
  tone = 'muted',
}: {
  title?: string;
  text: string;
  tone?: 'muted' | 'danger';
}) {
  return (
    <Card className={tone === 'danger' ? 'ui-feedback ui-feedback--danger' : 'ui-feedback'}>
      <CardContent className="ui-feedback__content">
        <Icon>
          {tone === 'danger' ? (
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path
                d="M12 9v5m0 4h.01M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0Z"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          ) : (
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path
                d="M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10Z"
                stroke="currentColor"
                strokeWidth="2"
              />
              <path d="M12 8h.01" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
              <path d="M11 12h1v6h1" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
            </svg>
          )}
        </Icon>
        <div className="ui-feedback__text">
          {title ? <div className="ui-feedback__title">{title}</div> : null}
          <div className="ui-feedback__desc">{text}</div>
        </div>
      </CardContent>
    </Card>
  );
}

export function LoadingState({ text = '加载中...' }: { text?: string }) {
  return <Feedback title="请稍候" text={text} tone="muted" />;
}

export function EmptyState({ text = '暂无数据' }: { text?: string }) {
  return <Feedback title="暂无内容" text={text} tone="muted" />;
}

export function ErrorState({ text = '加载失败' }: { text?: string }) {
  return <Feedback title="出错了" text={text} tone="danger" />;
}

