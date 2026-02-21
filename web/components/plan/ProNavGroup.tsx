'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useMemo, useRef } from 'react';
import { cn } from '../ui/cn';
import { usePlan } from './PlanContext';
import { Badge } from '../ui/badge';
import { PRO_COPY } from '../../constants/pro';
import { toastComingSoon, toastProRequired, toastProRequiredAndRedirect } from '../../lib/pro-required-client';

function LockIcon({ size = 14 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
      style={{ flex: '0 0 auto' }}
    >
      <path
        d="M7.5 10V8.2C7.5 5.6 9.6 3.5 12.2 3.5C14.8 3.5 16.9 5.6 16.9 8.2V10"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
      />
      <path
        d="M6.8 10H17.6C18.5 10 19.2 10.7 19.2 11.6V18.2C19.2 19.1 18.5 19.8 17.6 19.8H6.8C5.9 19.8 5.2 19.1 5.2 18.2V11.6C5.2 10.7 5.9 10 6.8 10Z"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinejoin="round"
      />
    </svg>
  );
}

type NavItem = { key: string; label: string };

export default function ProNavGroup() {
  const pathname = usePathname();
  const plan = usePlan();
  const hoverThrottleRef = useRef<number>(0);

  const items: NavItem[] = useMemo(
    () => [
      { key: 'advanced_search', label: '高级搜索视图' },
      { key: 'benchmarks', label: '对标集合' },
      { key: 'upgrade', label: '专业版权益' },
    ],
    []
  );
  const hrefMap: Record<string, string> = {
    advanced_search: '/search?view=compact&sort=competition',
    benchmarks: '/benchmarks',
    upgrade: '/pro',
  };

  const onHoverFree = () => {
    const now = Date.now();
    if (now - hoverThrottleRef.current < 2500) return;
    hoverThrottleRef.current = now;
    toastProRequired();
  };

  const onClickFree = () => {
    toastProRequiredAndRedirect();
  };

  const onClickPro = () => {
    toastComingSoon();
  };

  const isFree = !plan.isPro && !plan.isAdmin;

  return (
    <div className="app-sidenav__section" style={{ marginTop: 6 }}>
      <div
        className="muted"
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '6px 10px 2px',
          fontSize: 12,
          letterSpacing: 0.2,
        }}
      >
        <span>高级分析</span>
        <Badge variant="muted">专业版</Badge>
      </div>

      {items.map((it) => {
        if (isFree) {
          return (
            <button
              key={it.key}
              type="button"
              className={cn('app-sidenav__item')}
              onMouseEnter={onHoverFree}
              onClick={onClickFree}
              style={{
                opacity: 0.65,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: 10,
              }}
            >
              <span>{it.label}</span>
              <LockIcon />
            </button>
          );
        }

        // Pro: implemented routes navigate normally; non-implemented routes show "coming soon".
        const href = hrefMap[it.key] || '#';
        const isImplemented = href !== '#';
        return (
          <Link
            key={it.key}
            href={href}
            className={cn('app-sidenav__item', isImplemented && pathname === href ? 'is-active' : undefined)}
            onClick={(e) => {
              if (!isImplemented) {
                e.preventDefault();
                onClickPro();
              }
            }}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: 10,
            }}
          >
            <span>{it.label}</span>
            <span className="muted" style={{ fontSize: 12 }}>
              {isImplemented ? '专业版' : PRO_COPY.toast.coming_soon_title}
            </span>
          </Link>
        );
      })}
    </div>
  );
}
