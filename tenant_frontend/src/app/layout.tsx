import type { Metadata, Viewport } from "next";
import "./globals.css";
import QueryProvider from "@/providers/QueryProvider";
import { Toaster } from "@/components/ui/sonner";
import SubdomainGuard from "@/components/SubdomainGuard";

// Fit the device width, allow the user to zoom (never lock it), and extend under phone notches.
export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  themeColor: "#0284c7",
};

// Installable as an app ("Add to home screen"), with its own icon.
export const metadata: Metadata = {
  title: "EduSekai",
  manifest: "/manifest.webmanifest",
  icons: { icon: "/icons/icon-192.png", apple: "/icons/icon-192.png" },
  appleWebApp: { capable: true, title: "EduSekai", statusBarStyle: "default" },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <QueryProvider>
          <SubdomainGuard>
            {children}
          </SubdomainGuard>
          <Toaster />
        </QueryProvider>
      </body>
    </html>
  );
}
