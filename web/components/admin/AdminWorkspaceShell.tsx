'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../ui/card';
import { Badge } from '../ui/badge';
import { cn } from '../ui/cn';
import { ADMIN_NAV_GROUPS, ADMIN_ROLE_ZH, ADMIN_TEXT, getAdminBreadcrumb } from '../../constants/admin-i18n';

type AdminMe = { id: number; email: string; role: string };

export default function AdminWorkspaceShell({
  me,
  children,
}: {
  me: AdminMe;
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const leaf = getAdminBreadcrumb(pathname || '/admin');
  const roleLabel = ADMIN_ROLE_ZH[me.role] || me.role;

  return (
    <div className="grid">
      <Card>
        <CardHeader>
          <CardTitle>{ADMIN_TEXT.workbenchTitle}</CardTitle>
          <CardDescription>{ADMIN_TEXT.breadcrumbFallback} / {leaf}</CardDescription>
        </CardHeader>
        <CardContent style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
          <Badge variant="muted">{me.email}</Badge>
          <Badge variant={me.role === 'admin' ? 'success' : 'muted'}>{roleLabel}</Badge>
          <span className="muted">ID #{me.id}</span>
          <span className="muted">·</span>
          <Link href="/" className="ui-btn ui-btn--secondary ui-btn--sm">
            返回前台
          </Link>
        </CardContent>
      </Card>

      <div className="admin-workspace">
        <Card>
          <CardHeader>
            <CardTitle>{ADMIN_TEXT.menuTitle}</CardTitle>
          </CardHeader>
          <CardContent className="admin-nav">
            {ADMIN_NAV_GROUPS.map((group) => (
              <div key={group.title} className="admin-nav__group">
                <div className="admin-nav__group-title">{group.title}</div>
                <div className="admin-nav__items">
                  {group.items.map((item) => {
                    const active =
                      pathname === item.href ||
                      (item.href === '/admin/sources' && pathname?.startsWith('/admin/data-sources')) ||
                      (item.href !== '/admin' && pathname?.startsWith(item.href));
                    return (
                      <Link key={item.href} href={item.href} className={cn('admin-nav__item', active ? 'is-active' : undefined)}>
                        <span className="admin-nav__icon" aria-hidden="true">
                          {item.icon}
                        </span>
                        <span>{item.label}</span>
                      </Link>
                    );
                  })}
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
        <div>{children}</div>
      </div>
    </div>
  );
}
