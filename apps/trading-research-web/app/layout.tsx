import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Trading Research Platform",
  description: "Private research dashboard for TradingView strategy analysis.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
