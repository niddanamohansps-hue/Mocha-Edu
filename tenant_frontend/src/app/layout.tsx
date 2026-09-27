import "./globals.css";
import QueryProvider from "@/providers/QueryProvider";
import { Toaster } from "@/components/ui/sonner";
import SubdomainGuard from "@/components/SubdomainGuard";

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
