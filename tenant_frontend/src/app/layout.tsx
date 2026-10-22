import type { Viewport } from "next";
import "./globals.css";
import QueryProvider from "@/providers/QueryProvider";
import { Toaster } from "@/components/ui/sonner";
import SubdomainGuard from "@/components/SubdomainGuard";

// Fit the device width, allow the user to zoom (never lock it), and extend under phone notches.
export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
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
