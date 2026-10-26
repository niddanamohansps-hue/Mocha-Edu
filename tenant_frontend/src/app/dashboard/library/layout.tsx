"use client";

import { ReactNode } from "react";
import { LibraryNav } from "@/components/dashboard/library/shared";

export default function LibraryLayout({ children }: { children: ReactNode }) {
    return (
        <div className="space-y-6">
            <LibraryNav />
            {children}
        </div>
    );
}
