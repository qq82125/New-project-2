import './globals.css';
import type { Metadata } from 'next';
import Shell from '../components/shell';
import { Toaster } from '../components/ui/toaster';

export const metadata: Metadata = {
  title: 'IVD产品雷达',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body>
        <Shell>{children}</Shell>
        <Toaster />
      </body>
    </html>
  );
}
