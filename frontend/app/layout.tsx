import type { Metadata } from "next";
import { Geist_Mono, Plus_Jakarta_Sans } from "next/font/google";
import Script from "next/script";
import { Toaster } from "@/components/ui/sonner";
import { APPEARANCE_BOOT } from "@/lib/appearance";
import "./globals.css";

const jakarta = Plus_Jakarta_Sans({ subsets: ["latin"], variable: "--font-jakarta", display: "swap" });
const geistMono = Geist_Mono({ subsets: ["latin"], variable: "--font-geist-mono", display: "swap" });

export const metadata: Metadata = {
  title: { default: "DocIntel", template: "%s | DocIntel" },
  description: "Upload invoices, monitor extraction, review and correct results, and search processed documents.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    // The theme class is set before hydration by the boot script, so React must not flag the mismatch.
    <html lang="en" className={`${jakarta.variable} ${geistMono.variable}`} suppressHydrationWarning>
      <body className="min-h-svh font-sans antialiased">
        <Script id="appearance-boot" strategy="beforeInteractive">
          {APPEARANCE_BOOT}
        </Script>
        {children}
        <Toaster />
      </body>
    </html>
  );
}
