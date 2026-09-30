import type { Metadata } from 'next';
import './globals.css';
import Link from 'next/link';

export const metadata: Metadata = {
  title: 'RAG Demo | Azure AI Foundry',
  description: 'Explorador visual de RAG con Azure AI Foundry y agentes locales',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="es">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet" />
      </head>
      <body>
        <div className="app-container">
          <aside className="sidebar">
            <div className="sidebar-logo">
              ⚡ <span>RAG Demo</span>
            </div>
            <nav className="nav-menu">
              <Link href="/" className="nav-item">
                🏠 Inicio
              </Link>
              <Link href="/documents" className="nav-item">
                📄 Explorador Docs
              </Link>
              <Link href="/chat" className="nav-item">
                💬 Chat Foundry
              </Link>
              <Link href="/playground" className="nav-item">
                ⚖️ Comparativa Rerank
              </Link>
            </nav>
          </aside>
          
          <main className="main-content">
            {children}
          </main>
        </div>
      </body>
    </html>
  );
}
