import './globals.css';
import type { Metadata } from 'next';
import Shell from '../components/shell';
import { Toaster } from '../components/ui/toaster';
import { getMe } from '../lib/getMe';
import { PlanProvider } from '../components/plan/PlanContext';

export const metadata: Metadata = {
  title: 'IVD产品雷达',
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const me = await getMe();
  const initialPlan = me
    ? {
        isPro: Boolean(me.plan?.is_pro),
        isAdmin: Boolean(me.plan?.is_admin),
        planStatus: String(me.plan?.plan_status || 'inactive'),
        expiresAt: (me.plan?.plan_expires_at as string | null) || null,
      }
    : null;
  return (
    <html lang="zh-CN">
      <body>
        <PlanProvider initialPlan={initialPlan}>
          <Shell>{children}</Shell>
        </PlanProvider>
        <Toaster />
      </body>
    </html>
  );
}
