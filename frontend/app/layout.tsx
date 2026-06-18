import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Scaletopia Evergreen",
  description: "Feed and explore the Evergreen memory",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className="mx-auto max-w-6xl px-5 py-6">
          <header className="mb-8 flex items-center justify-between">
            <Link href="/" className="flex items-center gap-2">
              <span className="text-lg font-semibold">🌲 Scaletopia Evergreen</span>
            </Link>
            <nav className="flex gap-2 text-sm">
              <Link href="/" className="btn-ghost">Clients</Link>
              <Link href="/graph" className="btn-ghost">Graph</Link>
              <Link href="/search" className="btn-ghost">Search</Link>
              <Link href="/clients/new" className="btn">+ New client</Link>
            </nav>
          </header>
          {children}
        </div>
      </body>
    </html>
  );
}
