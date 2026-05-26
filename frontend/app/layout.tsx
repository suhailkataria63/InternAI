
import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "InternAI — AI Internship Copilot",
  description: "Production-ready AI internship application analyzer with resume parsing, match scoring, roadmap generation, and application tracking.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>
        <div className="background-grid" />
        <div className="background-glow glow-1" />
        <div className="background-glow glow-2" />
        {children}
      </body>
    </html>
  );
}
