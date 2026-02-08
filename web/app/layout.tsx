import './globals.css';
import Link from 'next/link';

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body>
        <main>
          <header className="card">
            <h1>NMPA IVD 注册情报看板</h1>
            <nav className="topnav">
              <Link href="/">Dashboard</Link>
              <Link href="/search">Search</Link>
              <Link href="/status">Status</Link>
            </nav>
          </header>
          {children}
        </main>
      </body>
    </html>
  );
}
