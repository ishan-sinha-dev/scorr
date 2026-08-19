import type { Metadata } from "next";
import "./globals.css";

// Deliberately no next/font/google (Geist): it requires a build-time fetch
// to fonts.googleapis.com, which fails in network-restricted environments
// (this sandbox included, and plausibly enterprise/corporate networks this
// product's customers build behind). System font stack has no such
// dependency and is the simpler, single correct path for a B2B compliance
// app foundation.

export const metadata: Metadata = {
  title: "SOCRR — SOC Report Reviewer",
  description: "Evidence-linked control intelligence for SOC report review.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
