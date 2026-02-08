import './globals.css';
import Link from 'next/link';
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'IVD产品雷达',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body>
        <main>
          <header className="card">
            <h1>IVD产品雷达</h1>
            <nav className="topnav">
              <Link href="/">Dashboard</Link>
              <Link href="/search">Search</Link>
              <Link href="/status">Status</Link>
              <Link href="/admin">Admin</Link>
            </nav>
          </header>
          {children}
        </main>
      </body>
    </html>
  );
}
