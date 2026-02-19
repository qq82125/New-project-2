'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useRouter } from 'next/navigation';
import AuthNav from './AuthNav';
import { cn } from './ui/cn';
import { useAuth } from './auth/use-auth';
import ProNavGroup from './plan/ProNavGroup';

function isActivePath(pathname: string, href: string): boolean {
  if (href === '/') return pathname === '/';
  return pathname === href || pathname.startsWith(`${href}/`);
}

function AppHeader() {
  const auth = useAuth();
  const pathname = usePathname();
  const isAdmin = !auth.loading && auth.user?.role === 'admin';
  const navItems: Array<{ href: string; label: string }> = [
    { href: '/', label: '仪表盘' },
    { href: '/search', label: '搜索' },
    { href: '/subscriptions', label: '订阅与投递' },
  ];

  return (
    <header className="app-header">
      <div className="app-header__inner">
        <div className="app-brand">
          <div className="app-logo" aria-hidden="true">
            <span />
          </div>
          <div className="app-brand__text">
            <div className="app-brand__name">IVD智慧大脑</div>
            <div className="app-brand__tag">仪表盘 / 搜索 / 订阅与投递</div>
          </div>
        </div>
        <nav className="app-header__nav" aria-label="顶部导航">
          {navItems.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={cn('app-header__nav-item', isActivePath(pathname, item.href) ? 'is-active' : undefined)}
            >
              {item.label}
            </Link>
          ))}
          {isAdmin ? (
            <Link href="/admin" className={cn('app-header__nav-item', isActivePath(pathname, '/admin') ? 'is-active' : undefined)}>
              Admin
            </Link>
          ) : null}
        </nav>
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
    { href: '/', label: '仪表盘' },
    { href: '/search', label: '搜索' },
    { href: '/subscriptions', label: '订阅与投递' },
    { href: '/account', label: '用户中心' },
  ];

  return (
    <aside className="app-sidenav" aria-label="主菜单">
      <div className="app-sidenav__section">
        {items.map((item) => {
          const active = isActivePath(pathname, item.href);
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
    </aside>
  );
}

function AppShell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const auth = useAuth();
  const isAdmin = !auth.loading && auth.user?.role === 'admin';
  const pathname = usePathname();
  const isAdminRoute = pathname.startsWith('/admin');

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
      <div className={cn('app-body', isAdminRoute ? 'app-body--single' : undefined)}>
        {!isAdminRoute ? <SideNav isAdmin={isAdmin} /> : null}
        <main className={cn('app-main', isAdminRoute ? 'app-main--full' : undefined)}>{children}</main>
      </div>
    </div>
  );
}

function AuthShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="auth-shell">
      <div className="auth-shell__inner">
        <Link href="/" className="auth-shell__brand">
          IVD智慧大脑
        </Link>
        {children}
        <p className="auth-shell__hint">登录后可查看仪表盘、搜索与状态页。</p>
      </div>
    </div>
  );
}

export default function Shell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isAuth = pathname === '/login' || pathname === '/register';
  return isAuth ? <AuthShell>{children}</AuthShell> : <AppShell>{children}</AppShell>;
}
