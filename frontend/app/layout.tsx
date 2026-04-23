import "./globals.css";
import type { Metadata } from "next";
import { Analytics } from "@vercel/analytics/react";

export const metadata: Metadata = {
  title: "Lenny SME — Ask the Podcast",
  description:
    "A Subject Matter Expert trained on every episode of Lenny's Podcast. Ask anything about product, growth, and career advice.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-parchment text-ink font-sans">
        {children}
        <Analytics />
      </body>
    </html>
  );
}
