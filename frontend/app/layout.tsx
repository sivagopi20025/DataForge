import type { Metadata } from "next";
import type React from "react";
import "./globals.css";
import { Providers } from "@/app/providers";
import { Sidebar } from "@/components/layout/sidebar";

export const metadata: Metadata = {
  title: "DataForge",
  description: "Generate, inject, validate, and export enterprise test datasets.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Providers>
          <div className="min-h-screen lg:pl-[280px]">
            <Sidebar />
            <main className="mx-auto max-w-[1800px] px-5 py-6 lg:px-8">{children}</main>
          </div>
        </Providers>
      </body>
    </html>
  );
}
