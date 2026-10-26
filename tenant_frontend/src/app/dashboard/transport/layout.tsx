"use client";

import { ReactNode } from "react";
import { TransportNav } from "@/components/dashboard/transport/shared";

export default function TransportLayout({ children }: { children: ReactNode }) {
    return (
        <div className="space-y-6">
            <TransportNav />
            {children}
        </div>
    );
}
