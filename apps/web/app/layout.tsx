import type { Metadata } from "next";
import { Inter } from "next/font/google";

import { AppProviders } from "@/components/app-providers";

import "./globals.css";

export const metadata: Metadata = {
  title: "AI Engineering Workspace",
  description: "AI-assisted software engineering workspace"
};

const inter = Inter({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-inter",
});

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning className={`${inter.variable} font-sans`}>
      <body className="antialiased">
        <AppProviders>{children}</AppProviders>
      </body>
    </html>
  );
}
