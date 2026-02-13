'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useRouter } from 'next/navigation';
import AuthNav from './AuthNav';
import { cn } from './ui/cn';
import { useAuth } from './auth/use-auth';
import ProNavGroup from './plan/ProNavGroup';

function AppHeader() {
  return (
    <header className="app-header">
      <div className="app-header__inner">
        <div className="app-brand">
          <div className="app-logo" aria-hidden="true">
            <span />
          </div>
          <div className="app-brand__text">
            <div className="app-brand__name">IVD产品雷达</div>
            <div className="app-brand__tag">Dashboard / 搜索 / 状态</div>
          </div>
        </div>
        <nav className="app-header__actions">
          <AuthNav />
        </nav>
      </div>
    </header>
  );
}

function SideNav({ isAdmin }: { isAdmin: boolean }) {
  const pathname = usePathname();
  const items: Array<{ href: string; label: string }> = [
    { href: '/', label: 'Dashboard' },
    { href: '/search', label: '搜索' },
    { href: '/status', label: '状态' },
    { href: '/account', label: '用户中心' },
  ];

  return (
    <aside className="app-sidenav" aria-label="主菜单">
      <div className="app-sidenav__section">
        {items.map((item) => {
          const active = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn('app-sidenav__item', active ? 'is-active' : undefined)}
            >
              {item.label}
            </Link>
          );
        })}
      </div>

      <ProNavGroup />

      <div className="app-sidenav__footer">
        {isAdmin ? (
          <>
            <Link
              href="/admin"
              className={cn('app-sidenav__item', pathname === '/admin' ? 'is-active' : undefined)}
            >
              管理后台
            </Link>
            <Link
              href="/admin/data-sources"
              className={cn(
                'app-sidenav__item',
                pathname.startsWith('/admin/data-sources') ? 'is-active' : undefined
              )}
            >
              数据源管理
            </Link>
            <Link
              href="/admin/users"
              className={cn('app-sidenav__item', pathname.startsWith('/admin/users') ? 'is-active' : undefined)}
            >
              用户与会员
            </Link>
            <Link
              href="/admin/contact"
              className={cn('app-sidenav__item', pathname.startsWith('/admin/contact') ? 'is-active' : undefined)}
            >
              联系信息
            </Link>
          </>
        ) : null}
      </div>
    </aside>
  );
}

function AppShell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const auth = useAuth();
  const isAdmin = !auth.loading && auth.user?.role === 'admin';
  const pathname = usePathname();

  // First-time onboarding redirect:
  // - after registration (explicit redirect), and also any time onboarded=false
  // - do not interrupt auth pages or the welcome/contact pages themselves
  if (
    !auth.loading &&
    auth.user &&
    auth.user.onboarded === false &&
    pathname !== '/welcome' &&
    pathname !== '/contact' &&
    pathname !== '/login' &&
    pathname !== '/register'
  ) {
    router.replace('/welcome');
    return null;
  }

  return (
    <div className="app-shell">
      <AppHeader />
      <div className="app-body">
        <SideNav isAdmin={isAdmin} />
        <main className="app-main">{children}</main>
      </div>
    </div>
  );
}

function AuthShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="auth-shell">
      <div className="auth-shell__inner">
        <Link href="/" className="auth-shell__brand">
          IVD产品雷达
        </Link>
        {children}
        <p className="auth-shell__hint">登录后可查看 Dashboard、搜索与状态页。</p>
      </div>
    </div>
  );
}

export default function Shell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isAuth = pathname === '/login' || pathname === '/register';
  return isAuth ? <AuthShell>{children}</AuthShell> : <AppShell>{children}</AppShell>;
}
