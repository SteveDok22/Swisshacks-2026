import type { Metadata } from "next";
import { Bitter, IBM_Plex_Mono } from "next/font/google";
import localFont from "next/font/local";
import { QueryProvider } from "@/components/QueryProvider";
import "./globals.css";

/**
 * Fonts — AMINA-aligned, self-hosted via next/font (no render-blocking CDN
 * @import, zero layout shift, available offline at runtime).
 *
 * - Satoshi (UI sans): not on Google Fonts, so self-hosted from the committed
 *   variable woff2. The variable axis (300–900) is what supplies a TRUE
 *   `font-semibold` (600) — the static cuts on Fontshare skip 600, which the
 *   old CDN @import silently fell back to faux-bold for.
 * - Bitter (serif display) + IBM Plex Mono (data): Google fonts, downloaded and
 *   self-hosted by next/font at build time.
 *
 * Each exposes a CSS variable consumed by tailwind.config.ts fontFamily.
 */
const satoshi = localFont({
  src: "./fonts/Satoshi-Variable.woff2",
  variable: "--font-sans",
  weight: "300 900",
  display: "swap",
});

const bitter = Bitter({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-serif",
  display: "swap",
});

const ibmPlexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Sentinel · Risk Intelligence",
  description: "AI-powered risk scoring and compliance review platform",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="en"
      className={`${satoshi.variable} ${bitter.variable} ${ibmPlexMono.variable}`}
    >
      <body className="grain">
        <QueryProvider>{children}</QueryProvider>
      </body>
    </html>
  );
}
