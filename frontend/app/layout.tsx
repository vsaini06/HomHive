import type { ReactNode } from "react";
import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "HomHive",
  description: "Household intelligence that turns evidence into action.",
  icons: { icon: [{url: "/favicon.ico", sizes: "any"}, {url: "/icon.png", type: "image/png"}], apple: "/branding/homhive-192.png" },
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
