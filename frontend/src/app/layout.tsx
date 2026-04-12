import type { Metadata } from "next";
import { GeistSans } from "geist/font/sans";
import { GeistMono } from "geist/font/mono";

import { Providers } from "@/components/Providers";

import "./globals.css";

export const metadata: Metadata = {
  title: "TruthLens AI",
  description:
    "Advanced AI-driven verification for text, images, and deepfake videos separating facts from fiction in real time.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <body
        className={`${GeistSans.variable} ${GeistMono.variable} min-h-screen bg-black font-sans text-zinc-400`}
      >
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
