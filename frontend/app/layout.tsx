import type { Metadata, Viewport } from "next";
import { Shell } from "@/components/layout/Shell";
import "./globals.css";

export const metadata: Metadata = {
  title: "URBIX",
  description: "Understand cities. Predict what comes next.",
  applicationName: "URBIX",
  appleWebApp: { capable: true, title: "URBIX", statusBarStyle: "black-translucent" },
};

export const viewport: Viewport = {
  themeColor: "#101826",
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&display=swap" rel="stylesheet" />
      </head>
      <body>
        <Shell>{children}</Shell>
      </body>
    </html>
  );
}
