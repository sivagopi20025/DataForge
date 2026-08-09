import type { Metadata } from "next";
import type React from "react";
import "./globals.css";
import { Providers } from "@/app/providers";
import { MobileNav, Sidebar } from "@/components/layout/sidebar";

export const metadata: Metadata = {
  title: "DataForge",
  description: "Generate, inject, validate, and export enterprise test datasets.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Providers>
          <div className="min-h-screen min-w-0 overflow-x-hidden lg:pl-[280px]">
            <Sidebar />
            <MobileNav />
            <main className="mx-auto min-w-0 max-w-[1800px] px-4 py-5 sm:px-5 lg:px-8">{children}</main>
          </div>
        </Providers>
      </body>
    </html>
  );
}
