import type { Metadata } from "next";
import { NextIntlClientProvider } from "next-intl";
import { getMessages } from "next-intl/server";
import { notFound } from "next/navigation";
import { routing } from "@/i18n/routing";
import { QueryProvider } from "@/components/providers/QueryProvider";
import { ThemeProvider } from "@/components/providers/ThemeProvider";
import { AuthProvider } from "@/components/providers/AuthProvider";
import { SyncProvider } from "@/components/providers/SyncProvider";
import { ToastProvider } from "@/components/ui/Toast";
import { RouteOverlays } from "@/components/layout/RouteOverlays";
import { Shell } from "@/components/layout/Shell";
import { TourProvider } from "@/components/help/TourProvider";
import "@/app/globals.css";

export const metadata: Metadata = {
  title: "Aifya — Hospital Management System",
  description: "AI-Native Hospital Management System for Kenyan hospitals",
  // Served from /public rather than the src/app metadata convention: Next 15
  // inlines the absolute source path into the generated metadata route, so a
  // checkout path containing an apostrophe fails to build.
  icons: { icon: "/brand/icon.svg" },
};

/**
 * Root layout for the application with locale support.
 * @param props.children - Page content
 * @param props.params - Route params containing locale
 * @returns Root HTML layout
 */
export default async function RootLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;

  if (!routing.locales.includes(locale as "en" | "sw")) {
    notFound();
  }

  const messages = await getMessages();

  return (
    <html lang={locale} suppressHydrationWarning>
      <body className="min-h-screen bg-background font-sans antialiased">
        <ThemeProvider>
          <NextIntlClientProvider messages={messages}>
            <QueryProvider>
              <AuthProvider>
                <SyncProvider>
                  <ToastProvider>
                    <TourProvider>
                      <Shell>{children}</Shell>
                      <RouteOverlays />
                    </TourProvider>
                  </ToastProvider>
                </SyncProvider>
              </AuthProvider>
            </QueryProvider>
          </NextIntlClientProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
