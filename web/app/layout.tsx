import './globals.css';
import Link from 'next/link';

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body>
        <main>
          <div className="card">
            <h1>NMPA IVD 注册/备案查询</h1>
            <nav>
              <Link href="/">搜索</Link> | <Link href="/status">更新状态</Link>
            </nav>
          </div>
          {children}
        </main>
      </body>
    </html>
  );
}
