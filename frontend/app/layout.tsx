import type { ReactNode } from "react";
import type { Metadata } from "next";
import "./globals.css";
import "./refined.css";

export const metadata: Metadata = {
  title: "HomHive",
  description: "Understand your home, discover what needs attention, and plan the next step with HomHive.",
  icons: { icon: [{url: "/favicon.ico", sizes: "any"}, {url: "/icon.png", type: "image/png"}], apple: "/branding/homhive-192.png" },
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
