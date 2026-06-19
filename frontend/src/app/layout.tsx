import type { Metadata } from "next";
import { QueryProvider } from "@/components/QueryProvider";
import "./globals.css";

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
    <html lang="en">
      <body className="grain">
        <QueryProvider>{children}</QueryProvider>
      </body>
    </html>
  );
}
