
import type { Metadata } from "next";
import Script from "next/script";
import { ThemeProvider } from "@/components/theme/ThemeProvider";
import { Toaster } from "@/components/control-ui/ui/toast";
import "./globals.css";

export const metadata: Metadata = {
  title: "InternAI — Your next application, with clarity",
  description: "Understand your fit, build relevant skills, and create grounded application writing with InternAI.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" data-theme="light" suppressHydrationWarning>
      <head>
        <Script id="internai-theme-init" strategy="beforeInteractive">
          {`try { var savedTheme = localStorage.getItem("internai-theme"); var prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches; document.documentElement.dataset.theme = savedTheme === "dark" || (savedTheme !== "light" && prefersDark) ? "dark" : "light"; } catch (_) {}`}
        </Script>
      </head>
      <body>
        <ThemeProvider>{children}<Toaster /></ThemeProvider>
      </body>
    </html>
  );
}
