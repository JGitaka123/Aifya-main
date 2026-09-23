import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Providers } from "./providers";
import { Header } from "@/components/Header";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Aifya Health Platform",
  description: "AI-powered clinical documentation and claims intelligence for Kenyan healthcare",
  manifest: "/manifest.json",
  themeColor: "#1e40af",
  viewport: "width=device-width, initial-scale=1, maximum-scale=5",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  // Script to prevent flash of wrong theme
  const themeScript = `
    (function() {
      try {
        var theme = localStorage.getItem('aifya_theme');
        if (theme === 'dark' || (!theme && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
          document.documentElement.classList.add('dark');
        }
      } catch(e) {}
    })();
  `;

  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body className={`${inter.className} transition-colors duration-200`}>
        {/* Skip to content link for accessibility */}
        <a
          href="#main-content"
          className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-[300] focus:px-4 focus:py-2 focus:bg-medical-blue focus:text-white focus:rounded-md focus:text-sm focus:font-medium"
        >
          Skip to main content
        </a>

        <Providers>
          <div className="min-h-screen bg-slate-50 dark:bg-slate-900 flex flex-col transition-colors print:bg-white">
            <Header />
            <main
              id="main-content"
              className="flex-1 max-w-7xl w-full mx-auto p-4 md:p-6 lg:p-8 print:max-w-none print:p-0"
              tabIndex={-1}
            >
              {children}
            </main>
            <footer className="py-4 text-center text-xs text-slate-400 dark:text-slate-600 border-t border-slate-200 dark:border-slate-800 print:hidden">
              Aifya Health Platform v1.0 &middot; Mary Help Hospital &middot; Powered by AI
            </footer>
          </div>
        </Providers>
      </body>
    </html>
  );
}
